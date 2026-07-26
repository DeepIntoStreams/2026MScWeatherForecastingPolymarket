# 18j Gamma metadata settlement-family audit

Generated: `2026-07-14 22:00:19 UTC`

## Purpose

This audit classifies Hong Kong Polymarket temperature contracts by settlement family before expanding the frozen 18i upper-tail baseline to a full HKO contract-event universe. The headline family is HKO Daily Extract one-decimal. Wunderground, airport, ambiguous and other settlement mechanisms are excluded from the main Hong Kong empirical sample.

## Input coverage

- Local processed rows loaded: `2608`

- Unique local event slugs: `80`

- Unique local market slugs: `821`

- API metadata records recovered: `1642`

- Deduplicated audited contract rows: `901`

- Preliminary admissible HKO event-contract rows: `730`


## Settlement-family summary

| settlement_family | contracts | admissible_hko_event_contracts | token_valid |
| --- | --- | --- | --- |
| HKO_Daily_Extract_one_decimal | 803 | 730 | 803 |
| ambiguous_or_unknown | 80 | 0 | 0 |
| Wunderground_or_airport | 18 | 0 | 18 |


## Contract-event-type summary

| contract_event_type | settlement_family | contracts | admissible_hko_event_contracts |
| --- | --- | --- | --- |
| interior_bin | HKO_Daily_Extract_one_decimal | 657 | 657 |
| upper_tail | HKO_Daily_Extract_one_decimal | 73 | 73 |
| unknown | ambiguous_or_unknown | 80 | 0 |
| lower_tail | HKO_Daily_Extract_one_decimal | 73 | 0 |
| interior_bin | Wunderground_or_airport | 14 | 0 |
| lower_tail | Wunderground_or_airport | 2 | 0 |
| upper_tail | Wunderground_or_airport | 2 | 0 |


## March 13 audit

The March 13 rows are singled out because external review suggested that some early Hong Kong markets may belong to a Wunderground / airport settlement family rather than the HKO Daily Extract one-decimal family.

| event_date | market_slug | market_question | group_item_title | settlement_family | contract_event_type | event_set | admissible_hko_event_contract | settlement_family_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-03-13 |  |  |  | ambiguous_or_unknown | unknown |  | False | Insufficient settlement-source evidence. |


## Preliminary admissible HKO contract-event universe preview

| event_date | market_slug | market_question | group_item_title | contract_event_type | event_set | settlement_family | selected_yes_token_id |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-04-02 | highest-temperature-in-hong-kong-on-april-1-2026-21c | Will the highest temperature in Hong Kong be 21°C on April 1? | 21°C | interior_bin | [1, 2) | HKO_Daily_Extract_one_decimal | 40014900626589044189029630768093662713815741737430235059361070842764241218823 |
| 2026-04-02 | highest-temperature-in-hong-kong-on-april-1-2026-22c | Will the highest temperature in Hong Kong be 22°C on April 1? | 22°C | interior_bin | [2, 3) | HKO_Daily_Extract_one_decimal | 55079827773872631729176930461884414860375524560638114135289382035970218663038 |
| 2026-04-02 | highest-temperature-in-hong-kong-on-april-1-2026-23c | Will the highest temperature in Hong Kong be 23°C on April 1? | 23°C | interior_bin | [3, 4) | HKO_Daily_Extract_one_decimal | 83841444489435774308014761014987456636927246644172209548916425298470168255910 |
| 2026-04-02 | highest-temperature-in-hong-kong-on-april-1-2026-24c | Will the highest temperature in Hong Kong be 24°C on April 1? | 24°C | interior_bin | [4, 5) | HKO_Daily_Extract_one_decimal | 44949916810529548120680678974005916291746611437060914085328650456191313099194 |
| 2026-04-02 | highest-temperature-in-hong-kong-on-april-1-2026-25c | Will the highest temperature in Hong Kong be 25°C on April 1? | 25°C | interior_bin | [5, 6) | HKO_Daily_Extract_one_decimal | 74029023981756759082197939119003286627001628189391619854668747272006096227673 |
| 2026-04-02 | highest-temperature-in-hong-kong-on-april-1-2026-26c | Will the highest temperature in Hong Kong be 26°C on April 1? | 26°C | interior_bin | [6, 7) | HKO_Daily_Extract_one_decimal | 43076841186972569954589188275745972187022313669271379429828637168322720934433 |
| 2026-04-02 | highest-temperature-in-hong-kong-on-april-1-2026-27c | Will the highest temperature in Hong Kong be 27°C on April 1? | 27°C | interior_bin | [7, 8) | HKO_Daily_Extract_one_decimal | 15286266942096997100441907272183828891275214701549879934850424172490056004762 |
| 2026-04-02 | highest-temperature-in-hong-kong-on-april-1-2026-28c | Will the highest temperature in Hong Kong be 28°C on April 1? | 28°C | interior_bin | [8, 9) | HKO_Daily_Extract_one_decimal | 2217105085674160947057305310232537454370298167764248642073346728367195238715 |
| 2026-04-02 | highest-temperature-in-hong-kong-on-april-1-2026-29c | Will the highest temperature in Hong Kong be 29°C on April 1? | 29°C | interior_bin | [9, 10) | HKO_Daily_Extract_one_decimal | 13757421407633171963826033095139937965738957582512295012829992103522849849893 |
| 2026-04-02 | highest-temperature-in-hong-kong-on-april-1-2026-30corhigher | Will the highest temperature in Hong Kong be 30°C or higher on April 1? | 30°C or higher | upper_tail | [10, infinity) | HKO_Daily_Extract_one_decimal | 20796348205047967733869729627896331196596616742840951445748283819848266836944 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-10-2026-21c | Will the highest temperature in Hong Kong be 21°C on April 10? | 21°C | interior_bin | [1, 2) | HKO_Daily_Extract_one_decimal | 54836983936980878212606421868210803097902568402169344278015434270494268497477 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-10-2026-22c | Will the highest temperature in Hong Kong be 22°C on April 10? | 22°C | interior_bin | [2, 3) | HKO_Daily_Extract_one_decimal | 64601735238886796622927629959507020019160609939140331765301887751898128552410 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-10-2026-23c | Will the highest temperature in Hong Kong be 23°C on April 10? | 23°C | interior_bin | [3, 4) | HKO_Daily_Extract_one_decimal | 27108372496993268654926442590603826923879365862633957505324227158731269160365 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-10-2026-24c | Will the highest temperature in Hong Kong be 24°C on April 10? | 24°C | interior_bin | [4, 5) | HKO_Daily_Extract_one_decimal | 33920930266990684139171199131588879631620210162811979261259740749860755381977 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-10-2026-25c | Will the highest temperature in Hong Kong be 25°C on April 10? | 25°C | interior_bin | [5, 6) | HKO_Daily_Extract_one_decimal | 41642465981386783567093252900415715824417450066807872070855509555051948550405 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-10-2026-26c | Will the highest temperature in Hong Kong be 26°C on April 10? | 26°C | interior_bin | [6, 7) | HKO_Daily_Extract_one_decimal | 36850248312549903875364114577225516929899282555521479198145552785017591833115 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-10-2026-27c | Will the highest temperature in Hong Kong be 27°C on April 10? | 27°C | interior_bin | [7, 8) | HKO_Daily_Extract_one_decimal | 88262719188573566470251670873242729419758093265490171670915320458063421254960 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-10-2026-28c | Will the highest temperature in Hong Kong be 28°C on April 10? | 28°C | interior_bin | [8, 9) | HKO_Daily_Extract_one_decimal | 58956322473206871218357865379829554333961784487932969144570010590439148147860 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-10-2026-29c | Will the highest temperature in Hong Kong be 29°C on April 10? | 29°C | interior_bin | [9, 10) | HKO_Daily_Extract_one_decimal | 114221833123908158105887372263604526651035188443468358054614096591140838124990 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-10-2026-30corhigher | Will the highest temperature in Hong Kong be 30°C or higher on April 10? | 30°C or higher | upper_tail | [10, infinity) | HKO_Daily_Extract_one_decimal | 21410421144675005956027138392042585861329063186102722742002484227225248573706 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-11-2026-21c | Will the highest temperature in Hong Kong be 21°C on April 11? | 21°C | interior_bin | [1, 2) | HKO_Daily_Extract_one_decimal | 35879719803810768508611009685428510433959413848777763007743594550055939964018 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-11-2026-22c | Will the highest temperature in Hong Kong be 22°C on April 11? | 22°C | interior_bin | [2, 3) | HKO_Daily_Extract_one_decimal | 12794935403832978907597576149827725505165804525101254774030044540293910764702 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-11-2026-23c | Will the highest temperature in Hong Kong be 23°C on April 11? | 23°C | interior_bin | [3, 4) | HKO_Daily_Extract_one_decimal | 45708551049554033634350032853753718009141030316149444142960545499853150869971 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-11-2026-24c | Will the highest temperature in Hong Kong be 24°C on April 11? | 24°C | interior_bin | [4, 5) | HKO_Daily_Extract_one_decimal | 71015926237664695819190069349633226964696933882377479362384588034762150762857 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-11-2026-25c | Will the highest temperature in Hong Kong be 25°C on April 11? | 25°C | interior_bin | [5, 6) | HKO_Daily_Extract_one_decimal | 76783062408906872327708539394668637558494963875845953992950843706271674508706 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-11-2026-26c | Will the highest temperature in Hong Kong be 26°C on April 11? | 26°C | interior_bin | [6, 7) | HKO_Daily_Extract_one_decimal | 115323362012133967493704850051604257679341456620719145674170295163942973964852 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-11-2026-27c | Will the highest temperature in Hong Kong be 27°C on April 11? | 27°C | interior_bin | [7, 8) | HKO_Daily_Extract_one_decimal | 82778080487551185763334075014686932270091422590989760299055816825048372587854 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-11-2026-28c | Will the highest temperature in Hong Kong be 28°C on April 11? | 28°C | interior_bin | [8, 9) | HKO_Daily_Extract_one_decimal | 73712799162388775159427291550890203203666102742449442433252430982779807784372 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-11-2026-29c | Will the highest temperature in Hong Kong be 29°C on April 11? | 29°C | interior_bin | [9, 10) | HKO_Daily_Extract_one_decimal | 36143562334637565063970049458654785003551167675901869757774239018369416172106 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-11-2026-30corhigher | Will the highest temperature in Hong Kong be 30°C or higher on April 11? | 30°C or higher | upper_tail | [10, infinity) | HKO_Daily_Extract_one_decimal | 109670798574747185853429891426457365783370233096204837880877997939129390812751 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-12-2026-21c | Will the highest temperature in Hong Kong be 21°C on April 12? | 21°C | interior_bin | [1, 2) | HKO_Daily_Extract_one_decimal | 95407826925914946336643405384501184976180641795062108114518961575661241514277 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-12-2026-22c | Will the highest temperature in Hong Kong be 22°C on April 12? | 22°C | interior_bin | [2, 3) | HKO_Daily_Extract_one_decimal | 83662538222777860292389767984263238962567802565862327556198814758385298659816 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-12-2026-23c | Will the highest temperature in Hong Kong be 23°C on April 12? | 23°C | interior_bin | [3, 4) | HKO_Daily_Extract_one_decimal | 71121808715390735640599054502498556858825656848951017405299226650847282719271 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-12-2026-24c | Will the highest temperature in Hong Kong be 24°C on April 12? | 24°C | interior_bin | [4, 5) | HKO_Daily_Extract_one_decimal | 98056206886920395187063628887347265100972900393545487973318684899311317533554 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-12-2026-25c | Will the highest temperature in Hong Kong be 25°C on April 12? | 25°C | interior_bin | [5, 6) | HKO_Daily_Extract_one_decimal | 100333235281670465080071734788280366907376455625839464815730335050100061014823 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-12-2026-26c | Will the highest temperature in Hong Kong be 26°C on April 12? | 26°C | interior_bin | [6, 7) | HKO_Daily_Extract_one_decimal | 97222777706577848036961102988169046243923427138308254842001548461519760593317 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-12-2026-27c | Will the highest temperature in Hong Kong be 27°C on April 12? | 27°C | interior_bin | [7, 8) | HKO_Daily_Extract_one_decimal | 108947040358953994279545569359514292704251194307921803827466610331634022413754 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-12-2026-28c | Will the highest temperature in Hong Kong be 28°C on April 12? | 28°C | interior_bin | [8, 9) | HKO_Daily_Extract_one_decimal | 70877020873068393683668313520728986915239094865319327014117538689679159285073 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-12-2026-29c | Will the highest temperature in Hong Kong be 29°C on April 12? | 29°C | interior_bin | [9, 10) | HKO_Daily_Extract_one_decimal | 82751711863239094682915780023947413340015851545585231421153333500088775544090 |
| 2026-04-13 | highest-temperature-in-hong-kong-on-april-12-2026-30corhigher | Will the highest temperature in Hong Kong be 30°C or higher on April 12? | 30°C or higher | upper_tail | [10, infinity) | HKO_Daily_Extract_one_decimal | 42534833793131152787940940650462504736697545275448677657744052058459793675583 |
| 2026-04-14 | highest-temperature-in-hong-kong-on-april-13-2026-22c | Will the highest temperature in Hong Kong be 22°C on April 13? | 22°C | interior_bin | [1, 2) | HKO_Daily_Extract_one_decimal | 99293621040730549325231814820410610832547732350335020675054652276589174114357 |
| 2026-04-14 | highest-temperature-in-hong-kong-on-april-13-2026-23c | Will the highest temperature in Hong Kong be 23°C on April 13? | 23°C | interior_bin | [2, 3) | HKO_Daily_Extract_one_decimal | 89916957096136682132924917633634048025087476514235776938773942283886309924625 |
| 2026-04-14 | highest-temperature-in-hong-kong-on-april-13-2026-24c | Will the highest temperature in Hong Kong be 24°C on April 13? | 24°C | interior_bin | [3, 4) | HKO_Daily_Extract_one_decimal | 29080195822267444386165649910402364530099441450849530341043845767837347461061 |
| 2026-04-14 | highest-temperature-in-hong-kong-on-april-13-2026-25c | Will the highest temperature in Hong Kong be 25°C on April 13? | 25°C | interior_bin | [4, 5) | HKO_Daily_Extract_one_decimal | 115174939423224925168740068794692759585238904168976538381937391113259374197047 |
| 2026-04-14 | highest-temperature-in-hong-kong-on-april-13-2026-26c | Will the highest temperature in Hong Kong be 26°C on April 13? | 26°C | interior_bin | [5, 6) | HKO_Daily_Extract_one_decimal | 62099603512781579860973431102523682933703135157382610058975557882648191716596 |
| 2026-04-14 | highest-temperature-in-hong-kong-on-april-13-2026-27c | Will the highest temperature in Hong Kong be 27°C on April 13? | 27°C | interior_bin | [6, 7) | HKO_Daily_Extract_one_decimal | 34491913205221681463207044821744867829885565533570547467894534209265318155741 |
| 2026-04-14 | highest-temperature-in-hong-kong-on-april-13-2026-28c | Will the highest temperature in Hong Kong be 28°C on April 13? | 28°C | interior_bin | [7, 8) | HKO_Daily_Extract_one_decimal | 71620471481517480702473693260939429946258855782517416458483748133540376045129 |
| 2026-04-14 | highest-temperature-in-hong-kong-on-april-13-2026-29c | Will the highest temperature in Hong Kong be 29°C on April 13? | 29°C | interior_bin | [8, 9) | HKO_Daily_Extract_one_decimal | 22221388475281013860848007538942977086708290425322534714785647078464038861994 |
| 2026-04-14 | highest-temperature-in-hong-kong-on-april-13-2026-30c | Will the highest temperature in Hong Kong be 30°C on April 13? | 30°C | interior_bin | [9, 10) | HKO_Daily_Extract_one_decimal | 101611528061924439869750543339188192462591036912302611110969858486926507729000 |
| 2026-04-14 | highest-temperature-in-hong-kong-on-april-13-2026-31corhigher | Will the highest temperature in Hong Kong be 31°C or higher on April 13? | 31°C or higher | upper_tail | [10, infinity) | HKO_Daily_Extract_one_decimal | 14097171019495854480993041567939052141066319840357605075917546750909592860309 |
| 2026-04-15 | highest-temperature-in-hong-kong-on-april-14-2026-21c | Will the highest temperature in Hong Kong be 21°C on April 14? | 21°C | interior_bin | [1, 2) | HKO_Daily_Extract_one_decimal | 66641798241165753211489903705246684777385274370533677356411419213464933438987 |
| 2026-04-15 | highest-temperature-in-hong-kong-on-april-14-2026-22c | Will the highest temperature in Hong Kong be 22°C on April 14? | 22°C | interior_bin | [2, 3) | HKO_Daily_Extract_one_decimal | 13370546282065697473371729572242097824239918684499475220284240858935920723041 |
| 2026-04-15 | highest-temperature-in-hong-kong-on-april-14-2026-23c | Will the highest temperature in Hong Kong be 23°C on April 14? | 23°C | interior_bin | [3, 4) | HKO_Daily_Extract_one_decimal | 113207127978191097885229707545567156326206459658678095990961358545827439600369 |
| 2026-04-15 | highest-temperature-in-hong-kong-on-april-14-2026-24c | Will the highest temperature in Hong Kong be 24°C on April 14? | 24°C | interior_bin | [4, 5) | HKO_Daily_Extract_one_decimal | 2328851494895717659133690267688489021646281569491861569206504975271186629895 |
| 2026-04-15 | highest-temperature-in-hong-kong-on-april-14-2026-25c | Will the highest temperature in Hong Kong be 25°C on April 14? | 25°C | interior_bin | [5, 6) | HKO_Daily_Extract_one_decimal | 31220456370460047001974226571142740576967519551640788680986594534826106551809 |
| 2026-04-15 | highest-temperature-in-hong-kong-on-april-14-2026-26c | Will the highest temperature in Hong Kong be 26°C on April 14? | 26°C | interior_bin | [6, 7) | HKO_Daily_Extract_one_decimal | 112889139991084195812349620505190241975235202968016305170084766813585327085701 |
| 2026-04-15 | highest-temperature-in-hong-kong-on-april-14-2026-27c | Will the highest temperature in Hong Kong be 27°C on April 14? | 27°C | interior_bin | [7, 8) | HKO_Daily_Extract_one_decimal | 13877836181753017167793295465122046990112502110510601480234694063678329353417 |
| 2026-04-15 | highest-temperature-in-hong-kong-on-april-14-2026-28c | Will the highest temperature in Hong Kong be 28°C on April 14? | 28°C | interior_bin | [8, 9) | HKO_Daily_Extract_one_decimal | 20341263943517209195091724322473110484518254189465116749974517703146002553256 |
| 2026-04-15 | highest-temperature-in-hong-kong-on-april-14-2026-29c | Will the highest temperature in Hong Kong be 29°C on April 14? | 29°C | interior_bin | [9, 10) | HKO_Daily_Extract_one_decimal | 38287895953980023815609167639954832336820963982937964017350700829859860447275 |
| 2026-04-15 | highest-temperature-in-hong-kong-on-april-14-2026-30corhigher | Will the highest temperature in Hong Kong be 30°C or higher on April 14? | 30°C or higher | upper_tail | [10, infinity) | HKO_Daily_Extract_one_decimal | 37469154916892071384543381829218229217717740835071670577695636049083897627097 |
| 2026-04-16 | highest-temperature-in-hong-kong-on-april-15-2026-21c | Will the highest temperature in Hong Kong be 21°C on April 15? | 21°C | interior_bin | [1, 2) | HKO_Daily_Extract_one_decimal | 31597152713066401714351153789917220579181049670186092718818019264003168301991 |
| 2026-04-16 | highest-temperature-in-hong-kong-on-april-15-2026-22c | Will the highest temperature in Hong Kong be 22°C on April 15? | 22°C | interior_bin | [2, 3) | HKO_Daily_Extract_one_decimal | 61987845043323177934129679021316900041876771071191229576825138543285066296461 |
| 2026-04-16 | highest-temperature-in-hong-kong-on-april-15-2026-23c | Will the highest temperature in Hong Kong be 23°C on April 15? | 23°C | interior_bin | [3, 4) | HKO_Daily_Extract_one_decimal | 72967961967480398642090394709558940770842347445291828200217599776104621012747 |
| 2026-04-16 | highest-temperature-in-hong-kong-on-april-15-2026-24c | Will the highest temperature in Hong Kong be 24°C on April 15? | 24°C | interior_bin | [4, 5) | HKO_Daily_Extract_one_decimal | 24586719670940893325491503095263308396844564257908058001178649176458858390320 |
| 2026-04-16 | highest-temperature-in-hong-kong-on-april-15-2026-25c | Will the highest temperature in Hong Kong be 25°C on April 15? | 25°C | interior_bin | [5, 6) | HKO_Daily_Extract_one_decimal | 31748117763642965908058216974394850891926323666700537269432608176683751935345 |
| 2026-04-16 | highest-temperature-in-hong-kong-on-april-15-2026-26c | Will the highest temperature in Hong Kong be 26°C on April 15? | 26°C | interior_bin | [6, 7) | HKO_Daily_Extract_one_decimal | 30847951656902599848442268900741662000804195973277813042774970500087686098227 |
| 2026-04-16 | highest-temperature-in-hong-kong-on-april-15-2026-27c | Will the highest temperature in Hong Kong be 27°C on April 15? | 27°C | interior_bin | [7, 8) | HKO_Daily_Extract_one_decimal | 59010406595208951889036271359750308579335796195927979946152381091189610697842 |
| 2026-04-16 | highest-temperature-in-hong-kong-on-april-15-2026-28c | Will the highest temperature in Hong Kong be 28°C on April 15? | 28°C | interior_bin | [8, 9) | HKO_Daily_Extract_one_decimal | 104664774560479599018761634997702357054043927749807836910462822701891848863380 |
| 2026-04-16 | highest-temperature-in-hong-kong-on-april-15-2026-29c | Will the highest temperature in Hong Kong be 29°C on April 15? | 29°C | interior_bin | [9, 10) | HKO_Daily_Extract_one_decimal | 45905243439724627261343671861961643965583073134822231461676508329733180622038 |
| 2026-04-16 | highest-temperature-in-hong-kong-on-april-15-2026-30corhigher | Will the highest temperature in Hong Kong be 30°C or higher on April 15? | 30°C or higher | upper_tail | [10, infinity) | HKO_Daily_Extract_one_decimal | 77021653073709144168795911772489396681307425253408147970760970371658735688869 |
| 2026-04-17 | highest-temperature-in-hong-kong-on-april-16-2026-21c | Will the highest temperature in Hong Kong be 21°C on April 16? | 21°C | interior_bin | [1, 2) | HKO_Daily_Extract_one_decimal | 5913641206172387752962597144057924402358239060171002371156135215423927584834 |
| 2026-04-17 | highest-temperature-in-hong-kong-on-april-16-2026-22c | Will the highest temperature in Hong Kong be 22°C on April 16? | 22°C | interior_bin | [2, 3) | HKO_Daily_Extract_one_decimal | 24531645722845287611812986318132210832705352889438715580291989356631184026338 |
| 2026-04-17 | highest-temperature-in-hong-kong-on-april-16-2026-23c | Will the highest temperature in Hong Kong be 23°C on April 16? | 23°C | interior_bin | [3, 4) | HKO_Daily_Extract_one_decimal | 91903937096889988385692177634143684361709747894120468684893410047829901955307 |
| 2026-04-17 | highest-temperature-in-hong-kong-on-april-16-2026-24c | Will the highest temperature in Hong Kong be 24°C on April 16? | 24°C | interior_bin | [4, 5) | HKO_Daily_Extract_one_decimal | 34435461563748604642799907585194831510570022784617329493032325149774980841993 |
| 2026-04-17 | highest-temperature-in-hong-kong-on-april-16-2026-25c | Will the highest temperature in Hong Kong be 25°C on April 16? | 25°C | interior_bin | [5, 6) | HKO_Daily_Extract_one_decimal | 5525050243761054467521962314594710839632041395683623770976821306042274383989 |
| 2026-04-17 | highest-temperature-in-hong-kong-on-april-16-2026-26c | Will the highest temperature in Hong Kong be 26°C on April 16? | 26°C | interior_bin | [6, 7) | HKO_Daily_Extract_one_decimal | 104927466918490130770860889602449057946561824438896283963293421930540277011262 |
| 2026-04-17 | highest-temperature-in-hong-kong-on-april-16-2026-27c | Will the highest temperature in Hong Kong be 27°C on April 16? | 27°C | interior_bin | [7, 8) | HKO_Daily_Extract_one_decimal | 44257849904292148716060129381998755183978924165497150254119649186580046120109 |
| 2026-04-17 | highest-temperature-in-hong-kong-on-april-16-2026-28c | Will the highest temperature in Hong Kong be 28°C on April 16? | 28°C | interior_bin | [8, 9) | HKO_Daily_Extract_one_decimal | 113038927596348619456532270695268761744058501537797580547787732755648546356450 |
| 2026-04-17 | highest-temperature-in-hong-kong-on-april-16-2026-29c | Will the highest temperature in Hong Kong be 29°C on April 16? | 29°C | interior_bin | [9, 10) | HKO_Daily_Extract_one_decimal | 107879621279143879080119755321860961453882763206109524172804879311021560328914 |
| 2026-04-17 | highest-temperature-in-hong-kong-on-april-16-2026-30corhigher | Will the highest temperature in Hong Kong be 30°C or higher on April 16? | 30°C or higher | upper_tail | [10, infinity) | HKO_Daily_Extract_one_decimal | 48048433716477505707695293112722186926089578768950552705404097789580119706471 |


## Interpretation

The audit identifies a non-empty preliminary set of admissible HKO Daily Extract one-decimal event contracts. These may include both upper-tail contracts and interior-bin contracts where metadata or rule evidence supports the interpretation. This supports the updated empirical direction: Hong Kong can be expanded from an upper-tail-only pilot into a full contract-event framework, provided settlement-family filtering is enforced before scoring, postprocessing and trading simulation.
