# 18f HKO Daily Extract and Polymarket historical panel to 2026-05-31

## Purpose

This pipeline constructs the March to May 2026 Hong Kong highest-temperature market panel by joining official HKO Daily Extract / metob maximum-temperature observations to deterministic Polymarket event slugs.

## Coverage

HKO rows: `92`

HKO date range: `2026-03-01` to `2026-05-31`


### HKO source labels

| hko_source_label   |   count |
|:-------------------|--------:|
| metob_plain        |      92 |


Polymarket event slugs swept: `80`

Gamma events found: `75`

Web pages found: `75`

Flattened child markets: `821`

Category validation rows: `821`

Upper-tail threshold rows: `75`

Price history rows: `0`

No-lookahead decision rows: `0`

Scoring-ready rows: `0`


## Upper-tail empirical role counts

| empirical_role                          |   count |
|:----------------------------------------|--------:|
| formally_certified_upper_tail_threshold |      73 |
| upper_tail_threshold_candidate          |       2 |


## Upper-tail sample preview

| event_date   |   threshold_K | market_slug                                                   |                                                                   yes_token_id |   hko_tmax_C |   Y_ge_K | empirical_role                          |
|:-------------|--------------:|:--------------------------------------------------------------|-------------------------------------------------------------------------------:|-------------:|---------:|:----------------------------------------|
| 2026-03-13   |            23 | highest-temperature-in-hong-kong-on-march-13-2026-23corhigher | 105079727049176982586460786683325690984261048416816328512834860964756914308798 |         21.8 |        0 | upper_tail_threshold_candidate          |
| 2026-03-14   |            24 | highest-temperature-in-hong-kong-on-march-14-2026-24corhigher |  59334591350541294762323929822958970303641554792870441284418817622760409799912 |         24.3 |        1 | upper_tail_threshold_candidate          |
| 2026-03-16   |            24 | highest-temperature-in-hong-kong-on-march-16-2026-24corhigher |  96547736760253325103867666165708769433810210787956568202716956033901110343233 |         24   |        1 | formally_certified_upper_tail_threshold |
| 2026-03-17   |            27 | highest-temperature-in-hong-kong-on-march-17-2026-27corhigher |  90201303442793564200994242062868707253275954439605696810946009562152635995543 |         24   |        0 | formally_certified_upper_tail_threshold |
| 2026-03-18   |            28 | highest-temperature-in-hong-kong-on-march-18-2026-28corhigher |  12268222159614728738434981709516892438897395269600915350011382182854202444351 |         27.8 |        0 | formally_certified_upper_tail_threshold |
| 2026-03-19   |            28 | highest-temperature-in-hong-kong-on-march-19-2026-28corhigher |  93249664553656843954425644598282848387760105568219245579096150666609197485978 |         28.1 |        1 | formally_certified_upper_tail_threshold |
| 2026-03-21   |            27 | highest-temperature-in-hong-kong-on-march-21-2026-27corhigher |  62955074773313067440933071197796382169974659936169570031288291349131182564927 |         22.3 |        0 | formally_certified_upper_tail_threshold |
| 2026-03-22   |            27 | highest-temperature-in-hong-kong-on-march-22-2026-27corhigher |  83566191575630565041831420482622256292186807187848065096514280278270420733054 |         25.4 |        0 | formally_certified_upper_tail_threshold |
| 2026-03-23   |            28 | highest-temperature-in-hong-kong-on-march-23-2026-28corhigher |   5969654045616989549233366740679567665880473089672120994014078507805960993240 |         27.4 |        0 | formally_certified_upper_tail_threshold |
| 2026-03-24   |            28 | highest-temperature-in-hong-kong-on-march-24-2026-28corhigher |  25774213028808917783935924032705159430534396020633061949453886501450333035247 |         26.9 |        0 | formally_certified_upper_tail_threshold |
| 2026-03-25   |            28 | highest-temperature-in-hong-kong-on-march-25-2026-28corhigher |  24347215888988629211141694053684838241376748257315236371809667481391911222804 |         30   |        1 | formally_certified_upper_tail_threshold |
| 2026-03-26   |            28 | highest-temperature-in-hong-kong-on-march-26-2026-28corhigher |  22969928800325737622836680162973924649247011171657024145402068845051583480077 |         28.4 |        1 | formally_certified_upper_tail_threshold |
| 2026-03-27   |            29 | highest-temperature-in-hong-kong-on-march-27-2026-29corhigher |  50060010016739109172171643437115576854369294678213890710065085897896957911280 |         26.2 |        0 | formally_certified_upper_tail_threshold |
| 2026-03-28   |            28 | highest-temperature-in-hong-kong-on-march-28-2026-28corhigher |  86239285114011274619793587954125983976639616193370774382729879159085660634638 |         27.4 |        0 | formally_certified_upper_tail_threshold |
| 2026-03-29   |            29 | highest-temperature-in-hong-kong-on-march-29-2026-29corhigher |  49518575885169443028098291806383472808522406412906840085439045945397205472313 |         25.8 |        0 | formally_certified_upper_tail_threshold |
| 2026-03-30   |            29 | highest-temperature-in-hong-kong-on-march-30-2026-29corhigher |  36817019254300225147073208483379722731819261539088743846141453885362287802985 |         28.3 |        0 | formally_certified_upper_tail_threshold |
| 2026-04-01   |            30 | highest-temperature-in-hong-kong-on-april-1-2026-30corhigher  |  20796348205047967733869729627896331196596616742840951445748283819848266836944 |         27.3 |        0 | formally_certified_upper_tail_threshold |
| 2026-04-02   |            28 | highest-temperature-in-hong-kong-on-april-2-2026-28corhigher  |  90893194109927421143921342032808825774651261426004539401108520429107664351857 |         24   |        0 | formally_certified_upper_tail_threshold |
| 2026-04-03   |            29 | highest-temperature-in-hong-kong-on-april-3-2026-29corhigher  |    489214184373807034980491617899152617536116229064820840303179512944737917580 |         27.1 |        0 | formally_certified_upper_tail_threshold |
| 2026-04-04   |            29 | highest-temperature-in-hong-kong-on-april-4-2026-29corhigher  |   2996870457162447764374213545916038777865761105147153068649138363626173049945 |         26.4 |        0 | formally_certified_upper_tail_threshold |
| 2026-04-05   |            29 | highest-temperature-in-hong-kong-on-april-5-2026-29corhigher  |  50409073537335131991936665136273430917848934617334036368110483089585055351802 |         25.7 |        0 | formally_certified_upper_tail_threshold |
| 2026-04-06   |            30 | highest-temperature-in-hong-kong-on-april-6-2026-30corhigher  |  43382942576271247142441321003283693526286321866069317184823908186687599298419 |         28.1 |        0 | formally_certified_upper_tail_threshold |
| 2026-04-07   |            30 | highest-temperature-in-hong-kong-on-april-7-2026-30corhigher  |  76937541284970235713946827721430827942510392819625643067124039675409412469066 |         29.2 |        0 | formally_certified_upper_tail_threshold |
| 2026-04-08   |            29 | highest-temperature-in-hong-kong-on-april-8-2026-29corhigher  |  72421226166215323078283475544953456189032019019011364844757743363733192096580 |         26.7 |        0 | formally_certified_upper_tail_threshold |
| 2026-04-09   |            29 | highest-temperature-in-hong-kong-on-april-9-2026-29corhigher  |  17428582223469959693261692788334178184676077266061986974015056550482061773293 |         28   |        0 | formally_certified_upper_tail_threshold |
| 2026-04-10   |            30 | highest-temperature-in-hong-kong-on-april-10-2026-30corhigher |  21410421144675005956027138392042585861329063186102722742002484227225248573706 |         28.3 |        0 | formally_certified_upper_tail_threshold |
| 2026-04-11   |            30 | highest-temperature-in-hong-kong-on-april-11-2026-30corhigher | 109670798574747185853429891426457365783370233096204837880877997939129390812751 |         27.6 |        0 | formally_certified_upper_tail_threshold |
| 2026-04-12   |            30 | highest-temperature-in-hong-kong-on-april-12-2026-30corhigher |  42534833793131152787940940650462504736697545275448677657744052058459793675583 |         28.5 |        0 | formally_certified_upper_tail_threshold |
| 2026-04-13   |            31 | highest-temperature-in-hong-kong-on-april-13-2026-31corhigher |  14097171019495854480993041567939052141066319840357605075917546750909592860309 |         29.7 |        0 | formally_certified_upper_tail_threshold |
| 2026-04-14   |            30 | highest-temperature-in-hong-kong-on-april-14-2026-30corhigher |  37469154916892071384543381829218229217717740835071670577695636049083897627097 |         29   |        0 | formally_certified_upper_tail_threshold |

## Market-only score summary

_No scoreable rows after price-history and decision-time filtering._

## Interpretation

The pipeline produced official HKO-aligned upper-tail contracts, but no scoreable decision-price rows. The remaining bottleneck is CLOB historical price availability for the recovered YES tokens.