# Notebook 02 Panel Construction

Notebook 02 constructs the deterministic weather sample used by the
probabilistic post-processing models.

## Candidate path

One candidate path is identified by its source, target date, decision rule and
forecast issue time. This definition follows the exact archived-source audit.

The request identifier is retained as provenance but is not used as the
run-level grouping key.

## Timestamp mapping

The hourly tables do not consistently carry both the issue time and applicable
decision time. These timestamps are recovered from the historical request
plans.

Request-plan columns are detected from their names and from their plausible
2025–2027 timestamp values. The selected request row is merged into the hourly
table by target date and decision rule.

The detected columns are recorded in:

`outputs/diagnostics/02_request_timestamp_mapping.csv`

## Complete Hong Kong local day

Forecast valid times are converted to `Asia/Hong_Kong`. An admitted path must
contain exactly 24 unique hourly positions on the target local date.

Repeated identical observations do not create additional support. Conflicting
temperatures for the same hour cause rejection.

## Information-time rule

The forecast issue time must not exceed the relevant decision time.

When more than one complete path is admissible for a target date and decision
rule, the latest admissible issue time is selected. Source preference resolves
only a tie at the same issue time.

## Daily maximum forecast

The deterministic daily maximum is reconstructed as the maximum of the 24
hourly forecasts.

The archived daily maximum table is used as a reconciliation check and is not
treated as an additional model.

## Training and evaluation

The weather training panel requires an admissible deterministic forecast and
the later official HKO outcome. It does not require a Polymarket market.

The market evaluation panel additionally requires a certified Polymarket event
book. It is therefore a subset of the weather training panel.

## Future refresh

The current official HKO panel ends on 30 June 2026. July and August can be
added without altering the path definition, time rules or sample separation.
