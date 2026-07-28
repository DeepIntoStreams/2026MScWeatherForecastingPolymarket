# Phase 3: Two-Year Weather Training Request Plan

## Purpose

Phase 3 creates the complete forecast request plan for the expanded
weather only training period.

No forecast data are downloaded in this phase. The phase establishes
the dates, cycles, request parameters, storage paths and integrity
conditions that will govern the later retrieval.

## Period design

The weather only training targets run from 16 March 2024 to
15 March 2026. This gives 730 target dates.

The request initialisation period begins on 14 March 2024. The two-day
buffer permits the earliest training target to be reconstructed later
under the earlier decision rules.

The request initialisation period ends on 15 March 2026. It therefore
precedes the weather plus market training period beginning on
16 March 2026.

June 2026 remains the out of sample validation period. July 2026 is a
planned later extension and is not included in the present plan.

## Cycle policy

The 00 and 12 UTC cycles are the core historical cycles. They are
selected for bulk retrieval.

The 06 and 18 UTC cycles are listed in the complete request register
but are not selected for bulk retrieval because their historical
availability is incomplete.

This preserves a simple and consistent two-year training source while
retaining a record of the supplementary cycles.

## Request volume

The plan contains:

- 730 weather only training target dates;
- 732 request initialisation dates, including the two-day buffer;
- 1,464 selected core requests;
- 1,464 supplementary documented requests;
- 2,928 total request-plan rows.

Each weather only target date is supported by the two core cycles on
the target date and the preceding two dates. This gives six planned
core requests for every target date.

## Evidential boundary

Phase 3 does not:

- make network requests;
- download the two-year forecast archive;
- access Polymarket prices;
- access realised market outcomes;
- fit or select a probabilistic model;
- select calibration parameters;
- calculate forecast scores;
- select a trading strategy;
- calculate trading returns;
- modify the certified Version 1 release.

## Next phase

Phase 4 will retrieve the selected 00 and 12 UTC requests, preserve
the raw responses, record failures explicitly and certify the actual
historical coverage.
