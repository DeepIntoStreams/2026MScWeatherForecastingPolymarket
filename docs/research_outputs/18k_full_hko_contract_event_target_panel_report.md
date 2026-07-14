# 18k full HKO contract-event target panel

Generated: `2026-07-14 22:49:21 UTC`

## Purpose

This step converts the repaired 18j v2 HKO contract-event universe into a realised target panel. It joins each certified HKO Daily Extract one-decimal contract to the official HKO daily maximum temperature and computes the realised binary payoff for upper-tail, interior-bin and lower-endpoint contracts.

## Main result

- Input 18j v2 universe rows: `803`

- Admissible HKO event-contract rows: `803`

- Target-panel rows: `803`

- Ready target-panel rows: `803`

- Unique event dates: `73`

- Dates with exactly one Yes contract: `73` / `73`

- Dates passing full event-book validity: `73` / `73`


## Integrity checks

| check | passed | detail |
| --- | --- | --- |
| input_universe_nonempty | True | input rows=803 |
| admissible_universe_nonempty | True | admissible rows=803 |
| all_admissible_have_hko_value | True | missing HKO rows=0 |
| all_admissible_have_binary_payoff | True | missing Y rows=0 |
| all_dates_exactly_one_yes | True | bad dates=0 |
| all_dates_have_partition_endpoints | True | missing endpoint dates=0 |
| no_partition_gaps_or_overlaps | True | gap dates=0; overlap dates=0 |
| no_hko_value_conflicts | True | conflict dates=0 |
| target_panel_ready_nonempty | True | ready rows=803 |


## Event-type target summary

| contract_event_type_v2 | rows | ready_rows | yes_rows | outcome_rate | unique_dates |
| --- | --- | --- | --- | --- | --- |
| interior_bin | 657 | 657 | 60 | 0.091324200913242 | 73 |
| lower_tail_endpoint | 73 | 73 | 0 | 0.0 | 73 |
| upper_tail | 73 | 73 | 13 | 0.1780821917808219 | 73 |


## Date-level resolution summary preview

| event_date | n_contracts | hko_tmax_C | yes_count | exactly_one_yes | target_rows_ready | n_lower_tail_endpoint | n_interior_bin | n_upper_tail | has_lower_endpoint | has_upper_endpoint | n_intervals | partition_has_gap | partition_has_overlap | partition_gap_detail | partition_overlap_detail | date_book_valid |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-03-16 | 11 | 24.0 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-03-17 | 11 | 24.0 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-03-18 | 11 | 27.8 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-03-19 | 11 | 28.1 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-03-21 | 11 | 22.3 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-03-22 | 11 | 25.4 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-03-23 | 11 | 27.4 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-03-24 | 11 | 26.9 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-03-25 | 11 | 30.0 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-03-26 | 11 | 28.4 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-03-27 | 11 | 26.2 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-03-28 | 11 | 27.4 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-03-29 | 11 | 25.8 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-03-30 | 11 | 28.3 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-04-01 | 11 | 27.3 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-04-02 | 11 | 24.0 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-04-03 | 11 | 27.1 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-04-04 | 11 | 26.4 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-04-05 | 11 | 25.7 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-04-06 | 11 | 28.1 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-04-07 | 11 | 29.2 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-04-08 | 11 | 26.7 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-04-09 | 11 | 28.0 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-04-10 | 11 | 28.3 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-04-11 | 11 | 27.6 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-04-12 | 11 | 28.5 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-04-13 | 11 | 29.7 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-04-14 | 11 | 29.0 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-04-15 | 11 | 28.9 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-04-16 | 11 | 30.2 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-04-17 | 11 | 28.0 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-04-18 | 11 | 28.5 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-04-19 | 11 | 30.0 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-04-20 | 11 | 28.4 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-04-21 | 11 | 28.9 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-04-22 | 11 | 29.4 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-04-23 | 11 | 29.0 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-04-24 | 11 | 23.7 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-04-25 | 11 | 26.5 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |
| 2026-04-26 | 11 | 28.8 | 1 | True | 11 | 1 | 9 | 1 | True | True | 11 | False | False |  |  | True |


## Target-panel preview

| event_date | market_slug | group_item_title | contract_event_type_v2 | event_set_v2 | event_condition_v2 | hko_tmax_C | Y_event_int | selected_yes_token_id |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-04-01 | highest-temperature-in-hong-kong-on-april-1-2026-20corbelow | 20°C or below | lower_tail_endpoint | (-infinity, 21) | T_HKO < 21 | 27.3 | 0 | 8604720886787485019697790883292245503562985545875997741180261352304494220128 |
| 2026-04-01 | highest-temperature-in-hong-kong-on-april-1-2026-21c | 21°C | interior_bin | [21, 22) | 21 <= T_HKO < 22 | 27.3 | 0 | 40014900626589044189029630768093662713815741737430235059361070842764241218823 |
| 2026-04-01 | highest-temperature-in-hong-kong-on-april-1-2026-22c | 22°C | interior_bin | [22, 23) | 22 <= T_HKO < 23 | 27.3 | 0 | 55079827773872631729176930461884414860375524560638114135289382035970218663038 |
| 2026-04-01 | highest-temperature-in-hong-kong-on-april-1-2026-23c | 23°C | interior_bin | [23, 24) | 23 <= T_HKO < 24 | 27.3 | 0 | 83841444489435774308014761014987456636927246644172209548916425298470168255910 |
| 2026-04-01 | highest-temperature-in-hong-kong-on-april-1-2026-24c | 24°C | interior_bin | [24, 25) | 24 <= T_HKO < 25 | 27.3 | 0 | 44949916810529548120680678974005916291746611437060914085328650456191313099194 |
| 2026-04-01 | highest-temperature-in-hong-kong-on-april-1-2026-25c | 25°C | interior_bin | [25, 26) | 25 <= T_HKO < 26 | 27.3 | 0 | 74029023981756759082197939119003286627001628189391619854668747272006096227673 |
| 2026-04-01 | highest-temperature-in-hong-kong-on-april-1-2026-26c | 26°C | interior_bin | [26, 27) | 26 <= T_HKO < 27 | 27.3 | 0 | 43076841186972569954589188275745972187022313669271379429828637168322720934433 |
| 2026-04-01 | highest-temperature-in-hong-kong-on-april-1-2026-27c | 27°C | interior_bin | [27, 28) | 27 <= T_HKO < 28 | 27.3 | 1 | 15286266942096997100441907272183828891275214701549879934850424172490056004762 |
| 2026-04-01 | highest-temperature-in-hong-kong-on-april-1-2026-28c | 28°C | interior_bin | [28, 29) | 28 <= T_HKO < 29 | 27.3 | 0 | 2217105085674160947057305310232537454370298167764248642073346728367195238715 |
| 2026-04-01 | highest-temperature-in-hong-kong-on-april-1-2026-29c | 29°C | interior_bin | [29, 30) | 29 <= T_HKO < 30 | 27.3 | 0 | 13757421407633171963826033095139937965738957582512295012829992103522849849893 |
| 2026-04-01 | highest-temperature-in-hong-kong-on-april-1-2026-30corhigher | 30°C or higher | upper_tail | [30, infinity) | T_HKO >= 30 | 27.3 | 0 | 20796348205047967733869729627896331196596616742840951445748283819848266836944 |
| 2026-04-10 | highest-temperature-in-hong-kong-on-april-10-2026-20corbelow | 20°C or below | lower_tail_endpoint | (-infinity, 21) | T_HKO < 21 | 28.3 | 0 | 22949151863078752582196083265341890533083952581087552910627824170177285810469 |
| 2026-04-10 | highest-temperature-in-hong-kong-on-april-10-2026-21c | 21°C | interior_bin | [21, 22) | 21 <= T_HKO < 22 | 28.3 | 0 | 54836983936980878212606421868210803097902568402169344278015434270494268497477 |
| 2026-04-10 | highest-temperature-in-hong-kong-on-april-10-2026-22c | 22°C | interior_bin | [22, 23) | 22 <= T_HKO < 23 | 28.3 | 0 | 64601735238886796622927629959507020019160609939140331765301887751898128552410 |
| 2026-04-10 | highest-temperature-in-hong-kong-on-april-10-2026-23c | 23°C | interior_bin | [23, 24) | 23 <= T_HKO < 24 | 28.3 | 0 | 27108372496993268654926442590603826923879365862633957505324227158731269160365 |
| 2026-04-10 | highest-temperature-in-hong-kong-on-april-10-2026-24c | 24°C | interior_bin | [24, 25) | 24 <= T_HKO < 25 | 28.3 | 0 | 33920930266990684139171199131588879631620210162811979261259740749860755381977 |
| 2026-04-10 | highest-temperature-in-hong-kong-on-april-10-2026-25c | 25°C | interior_bin | [25, 26) | 25 <= T_HKO < 26 | 28.3 | 0 | 41642465981386783567093252900415715824417450066807872070855509555051948550405 |
| 2026-04-10 | highest-temperature-in-hong-kong-on-april-10-2026-26c | 26°C | interior_bin | [26, 27) | 26 <= T_HKO < 27 | 28.3 | 0 | 36850248312549903875364114577225516929899282555521479198145552785017591833115 |
| 2026-04-10 | highest-temperature-in-hong-kong-on-april-10-2026-27c | 27°C | interior_bin | [27, 28) | 27 <= T_HKO < 28 | 28.3 | 0 | 88262719188573566470251670873242729419758093265490171670915320458063421254960 |
| 2026-04-10 | highest-temperature-in-hong-kong-on-april-10-2026-28c | 28°C | interior_bin | [28, 29) | 28 <= T_HKO < 29 | 28.3 | 1 | 58956322473206871218357865379829554333961784487932969144570010590439148147860 |
| 2026-04-10 | highest-temperature-in-hong-kong-on-april-10-2026-29c | 29°C | interior_bin | [29, 30) | 29 <= T_HKO < 30 | 28.3 | 0 | 114221833123908158105887372263604526651035188443468358054614096591140838124990 |
| 2026-04-10 | highest-temperature-in-hong-kong-on-april-10-2026-30corhigher | 30°C or higher | upper_tail | [30, infinity) | T_HKO >= 30 | 28.3 | 0 | 21410421144675005956027138392042585861329063186102722742002484227225248573706 |
| 2026-04-11 | highest-temperature-in-hong-kong-on-april-11-2026-20corbelow | 20°C or below | lower_tail_endpoint | (-infinity, 21) | T_HKO < 21 | 27.6 | 0 | 99930559057710551029371876710342208093308728579790256394238027160576126928316 |
| 2026-04-11 | highest-temperature-in-hong-kong-on-april-11-2026-21c | 21°C | interior_bin | [21, 22) | 21 <= T_HKO < 22 | 27.6 | 0 | 35879719803810768508611009685428510433959413848777763007743594550055939964018 |
| 2026-04-11 | highest-temperature-in-hong-kong-on-april-11-2026-22c | 22°C | interior_bin | [22, 23) | 22 <= T_HKO < 23 | 27.6 | 0 | 12794935403832978907597576149827725505165804525101254774030044540293910764702 |
| 2026-04-11 | highest-temperature-in-hong-kong-on-april-11-2026-23c | 23°C | interior_bin | [23, 24) | 23 <= T_HKO < 24 | 27.6 | 0 | 45708551049554033634350032853753718009141030316149444142960545499853150869971 |
| 2026-04-11 | highest-temperature-in-hong-kong-on-april-11-2026-24c | 24°C | interior_bin | [24, 25) | 24 <= T_HKO < 25 | 27.6 | 0 | 71015926237664695819190069349633226964696933882377479362384588034762150762857 |
| 2026-04-11 | highest-temperature-in-hong-kong-on-april-11-2026-25c | 25°C | interior_bin | [25, 26) | 25 <= T_HKO < 26 | 27.6 | 0 | 76783062408906872327708539394668637558494963875845953992950843706271674508706 |
| 2026-04-11 | highest-temperature-in-hong-kong-on-april-11-2026-26c | 26°C | interior_bin | [26, 27) | 26 <= T_HKO < 27 | 27.6 | 0 | 115323362012133967493704850051604257679341456620719145674170295163942973964852 |
| 2026-04-11 | highest-temperature-in-hong-kong-on-april-11-2026-27c | 27°C | interior_bin | [27, 28) | 27 <= T_HKO < 28 | 27.6 | 1 | 82778080487551185763334075014686932270091422590989760299055816825048372587854 |
| 2026-04-11 | highest-temperature-in-hong-kong-on-april-11-2026-28c | 28°C | interior_bin | [28, 29) | 28 <= T_HKO < 29 | 27.6 | 0 | 73712799162388775159427291550890203203666102742449442433252430982779807784372 |
| 2026-04-11 | highest-temperature-in-hong-kong-on-april-11-2026-29c | 29°C | interior_bin | [29, 30) | 29 <= T_HKO < 30 | 27.6 | 0 | 36143562334637565063970049458654785003551167675901869757774239018369416172106 |
| 2026-04-11 | highest-temperature-in-hong-kong-on-april-11-2026-30corhigher | 30°C or higher | upper_tail | [30, infinity) | T_HKO >= 30 | 27.6 | 0 | 109670798574747185853429891426457365783370233096204837880877997939129390812751 |
| 2026-04-12 | highest-temperature-in-hong-kong-on-april-12-2026-20corbelow | 20°C or below | lower_tail_endpoint | (-infinity, 21) | T_HKO < 21 | 28.5 | 0 | 3132811527238312836263575614350430269923706889338590753719330223712337930127 |
| 2026-04-12 | highest-temperature-in-hong-kong-on-april-12-2026-21c | 21°C | interior_bin | [21, 22) | 21 <= T_HKO < 22 | 28.5 | 0 | 95407826925914946336643405384501184976180641795062108114518961575661241514277 |
| 2026-04-12 | highest-temperature-in-hong-kong-on-april-12-2026-22c | 22°C | interior_bin | [22, 23) | 22 <= T_HKO < 23 | 28.5 | 0 | 83662538222777860292389767984263238962567802565862327556198814758385298659816 |
| 2026-04-12 | highest-temperature-in-hong-kong-on-april-12-2026-23c | 23°C | interior_bin | [23, 24) | 23 <= T_HKO < 24 | 28.5 | 0 | 71121808715390735640599054502498556858825656848951017405299226650847282719271 |
| 2026-04-12 | highest-temperature-in-hong-kong-on-april-12-2026-24c | 24°C | interior_bin | [24, 25) | 24 <= T_HKO < 25 | 28.5 | 0 | 98056206886920395187063628887347265100972900393545487973318684899311317533554 |
| 2026-04-12 | highest-temperature-in-hong-kong-on-april-12-2026-25c | 25°C | interior_bin | [25, 26) | 25 <= T_HKO < 26 | 28.5 | 0 | 100333235281670465080071734788280366907376455625839464815730335050100061014823 |
| 2026-04-12 | highest-temperature-in-hong-kong-on-april-12-2026-26c | 26°C | interior_bin | [26, 27) | 26 <= T_HKO < 27 | 28.5 | 0 | 97222777706577848036961102988169046243923427138308254842001548461519760593317 |
| 2026-04-12 | highest-temperature-in-hong-kong-on-april-12-2026-27c | 27°C | interior_bin | [27, 28) | 27 <= T_HKO < 28 | 28.5 | 0 | 108947040358953994279545569359514292704251194307921803827466610331634022413754 |
| 2026-04-12 | highest-temperature-in-hong-kong-on-april-12-2026-28c | 28°C | interior_bin | [28, 29) | 28 <= T_HKO < 29 | 28.5 | 1 | 70877020873068393683668313520728986915239094865319327014117538689679159285073 |
| 2026-04-12 | highest-temperature-in-hong-kong-on-april-12-2026-29c | 29°C | interior_bin | [29, 30) | 29 <= T_HKO < 30 | 28.5 | 0 | 82751711863239094682915780023947413340015851545585231421153333500088775544090 |
| 2026-04-12 | highest-temperature-in-hong-kong-on-april-12-2026-30corhigher | 30°C or higher | upper_tail | [30, infinity) | T_HKO >= 30 | 28.5 | 0 | 42534833793131152787940940650462504736697545275448677657744052058459793675583 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-13-2026-21corbelow | 21°C or below | lower_tail_endpoint | (-infinity, 22) | T_HKO < 22 | 29.7 | 0 | 97738960646174405599492671120798975234473473891362512867142859636452668830264 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-13-2026-22c | 22°C | interior_bin | [22, 23) | 22 <= T_HKO < 23 | 29.7 | 0 | 99293621040730549325231814820410610832547732350335020675054652276589174114357 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-13-2026-23c | 23°C | interior_bin | [23, 24) | 23 <= T_HKO < 24 | 29.7 | 0 | 89916957096136682132924917633634048025087476514235776938773942283886309924625 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-13-2026-24c | 24°C | interior_bin | [24, 25) | 24 <= T_HKO < 25 | 29.7 | 0 | 29080195822267444386165649910402364530099441450849530341043845767837347461061 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-13-2026-25c | 25°C | interior_bin | [25, 26) | 25 <= T_HKO < 26 | 29.7 | 0 | 115174939423224925168740068794692759585238904168976538381937391113259374197047 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-13-2026-26c | 26°C | interior_bin | [26, 27) | 26 <= T_HKO < 27 | 29.7 | 0 | 62099603512781579860973431102523682933703135157382610058975557882648191716596 |


## Issues requiring review

_No target-panel issues detected._


## Interpretation

The 18k target panel passes all automated checks. This supports using the full certified HKO Daily Extract one-decimal contract-event universe as the main Hong Kong empirical target panel for market scoring, forecast alignment, supervised postprocessing and trading simulation.


## Output files

- `data/processed/18k_full_hko_contract_event_target_panel.csv`

- `data/processed/18k_hko_realised_outcomes_used.csv`

- `data/processed/18k_hko_contract_event_date_resolution_summary.csv`

- `data/processed/18k_hko_contract_event_type_target_summary.csv`

- `data/processed/18k_hko_contract_event_integrity_checks.csv`

- `data/processed/18k_hko_contract_event_target_issues.csv`

- `docs/research_outputs/18k_full_hko_contract_event_target_panel_report.md`

- `data/review_bundles/18k_review_bundle.zip`
