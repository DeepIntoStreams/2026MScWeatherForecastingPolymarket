# ECMWF timing-method reconciliation

The final empirical rebuild identified a discrepancy between the earlier V2
production support selector and the methodology frozen in the later dissertation
versions.

The V2 production selector retained the latest complete-day forecast whose run
initialisation was no later than the decision time.

The final dissertation methodology explicitly imposes a six-hour
interface-availability allowance and a core-before-repair cycle priority.

The final March–August pipeline therefore implements the dissertation
methodology:

1. issue time plus six hours must not exceed the decision time;
2. eligible 00/12 UTC core cycles are preferred;
3. 06/18 UTC cycles are admitted only when no valid core path is available;
4. the selected path must contain the complete 24-hour Hong Kong local day.

The old 2,920-row V2 weather panel is retained only to quantify the effect of
this methodological reconciliation. It is not used to force the new processed
forecasts to reproduce superseded selections.

This prevents the final empirical pipeline from silently back-fitting its
implementation to previously reported numbers.
