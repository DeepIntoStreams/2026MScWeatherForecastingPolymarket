# ECMWF timing-method reconciliation

The final empirical rebuild identified an implementation difference between the
earlier V2 forecast-support selector and the methodology frozen for the final
dissertation pipeline.

## Earlier V2 implementation

The historical V2 panel occasionally retained older fallback forecasts. Its
observed selected-run ages range from 4 to 52 hours at the corresponding
decision time.

Those selections remain useful as an audit reference, but they do not define the
final March-August pipeline.

## Final methodology

The final empirical pipeline implements the dissertation methodology directly:

1. impose the six-hour interface-availability allowance;
2. identify the latest eligible 00/12 UTC core issue;
3. attempt that operationally latest core issue;
4. if it is unavailable or lacks a complete Hong Kong local-day path, attempt
   the latest eligible 06/18 UTC repair issue;
5. if neither succeeds, retain the date-rule key as unsupported;
6. never substitute progressively older forecasts to manufacture support.

Thus every supported selected run is operationally recent under the fixed
decision-time geometry.

## Role of the historical V2 panel

The 2,920 historical V2 date-rule observations are retained only to quantify
the consequence of the methodological reconciliation.

The final pipeline does not require old and new selected runs or deterministic
daily maxima to be identical.

No old processed forecast is used to construct the new final panel.
