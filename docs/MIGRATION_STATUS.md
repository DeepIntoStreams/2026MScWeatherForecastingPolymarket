# Historical Notebook Migration Status

Archive branch:

`archive/17j-plus-18n-18y-20260726`

Historical notebooks inspected:

**72**

## Completed

- Complete archive branch and tag.
- Clean empirical branch.
- Exact notebook inventory.
- Migration classification.
- Notebook 00–01 archive source audit.
- Canonical configuration and manifest modules.
- Canonical settlement engine.
- Configuration and settlement tests.
- Canonical Notebook 00.
- Canonical Notebook 01 certification framework.

## Not yet claimed

- Real HKO source migration.
- Real Polymarket contract certification.
- Final July or August data.
- Expanded weather training panel.
- Any new empirical score or PnL result.

## Next implementation task

Migrate the latest valid HKO and contract source adapters into Notebook 01,
then build the deterministic forecast and expanded weather-training panel in
Notebook 02.

## Notebook 01 real source status

- Exact archive schema audit: complete.
- Structural date and interval detection: corrected.
- Canonical contract definitions: complete.
- Canonical HKO outcomes: complete.
- Real eleven-event certification: implemented.
- Forecast-time HKO admissibility: assigned to Notebook 02.

## Notebook 01 March-June completion

- March-May certified dates: 73.
- June contract source: recovered and certified.
- June HKO Daily Extract outcomes: recovered and certified.
- June dates added: 30.
- Final settlement dates: 103.
- Final contract-event rows: 1,133.
- Date range: 16 March to 30 June 2026.
- Eleven events per date: verified.
- One realised winner per date: verified.

## Notebook 02 ZIP-aware source foundation

- Ordinary forecast files inspected: complete.
- Preserved ZIP review bundles inspected: complete.
- June hourly deterministic forecasts: recovered.
- June daily maximum forecasts: recovered.
- Request plans and fetch inventories: materialised.
- Exact source hashes and schemas: recorded.
- Weather training and market evaluation samples: separated.
- Twenty-four-hour Hong Kong local path rule: declared.
- Random train-test splitting: prohibited.
- Exact issue-time and run-level panel construction: next task.

## Notebook 02 completed panels

- Exact hourly grouping audit: complete.
- Request-plan issue-time detection: complete.
- Request-plan decision-time detection: complete.
- Request timestamps merged by date and decision rule: complete.
- Twenty-four-hour Hong Kong local paths: enforced.
- No-lookahead rule: enforced.
- Latest admissible issue-time selection: implemented.
- Daily maximum reconstruction: complete.
- Archived daily maximum reconciliation: complete.
- Weather training panel: complete.
- Market evaluation forecast panel: complete.
- Canonical Notebook 02: generated.

## Notebook 02 support and chronology gate

- Full 103-date by four-rule support matrix: complete.
- Exact missing June date-rule combination: identified.
- March-May absence: audited.
- Preserved forecast source coverage: audited.
- Preserved HKO extension sources: audited.
- Source-level recovery candidates: recorded.
- Chronological blocks: not assigned prematurely.
- Random split: prohibited.
- Model fitting: blocked pending support expansion.
- Next task: recover earlier admissible forecast-HKO pairs.

## Verified historical forecast panel

- False HKO-name outcome classification: corrected.
- Verified historical forecast column: forecast_hko_daily_max_C.
- Historical hourly paths retained: 256.
- Historical dates retained: 72.
- Stored-versus-reconstructed discrepancy: zero.
- Unsupported historical request rows excluded: 36.
- Certified June rows retained: 119.
- Combined verified rows: 375.
- Combined verified dates: 102.
- Full 103-date support matrix: recorded.
- Chronological blocks: assigned from actual available dates.
- Four expanding development folds: certified.
- Holdout and external outcomes: locked.
- Model fitting: permitted.
- Next task: construct the simple probabilistic model families.

## Probabilistic model selection

- Candidate specification declared before fitting.
- Nine numerical candidates implemented.
- Five conceptual model families documented.
- Four chronological expanding folds used.
- Settlement date retained as the uncertainty unit.
- Ninety-nine quantiles produced for every available prediction.
- Date-level CRPS used as the primary score.
- Common-support comparison enforced.
- Paired one-standard-error parsimony rule implemented.
- Holdout outcomes inaccessible during selection.
- External-test outcomes inaccessible during selection.
- Selected specification recorded in a manifest.
- Next task: fit the selected specification and evaluate the locked periods.

## Continuous distribution calibration

- Locked Notebook 04 model used.
- Development OOF predictions used exclusively.
- Median-preserving dispersion transformation implemented.
- Seven scales declared before selection.
- Identity transformation included.
- Date-level CRPS retained as the sole selection score.
- Coverage and interval width treated as diagnostics only.
- Paired one-standard-error preference for minimal adjustment applied.
- Predictive median preservation tested.
- Quantile monotonicity tested.
- Holdout outcomes inaccessible.
- External-test outcomes inaccessible.
- Market data inaccessible.
- Event-probability regularisation deferred to a separate stage.
- Next task: fit the locked model and scale, then evaluate locked periods.

## Locked holdout and external predictions

- Notebook 04 model choice retained without alteration.
- Notebook 05 dispersion scale retained without alteration.
- Final fitting restricted to warm-up and development observations.
- Holdout outcomes excluded from final fitting.
- External outcomes excluded from final fitting.
- No refit performed after holdout.
- Ninety-nine quantiles generated for every retained prediction.
- Uncalibrated and calibrated distributions both retained.
- Predictive median preservation tested.
- Quantile monotonicity tested.
- Forecast issue-time admissibility tested.
- Realised outcomes excluded from prediction files.
- Continuous scores not calculated.
- Event probabilities not calculated.
- Market prices not accessed.
- Trading returns not calculated.
- Next task: evaluate the locked continuous distributions.

## Locked continuous evaluation

- Locked model choice retained.
- Locked continuous calibration scale retained.
- Realised HKO outcomes joined only after predictions were written.
- Raw deterministic, selected uncalibrated and selected calibrated forecasts
  evaluated.
- Holdout and June external results reported separately.
- Ninety-nine-quantile CRPS used.
- Settlement date used as the primary uncertainty unit.
- Median MAE and median bias reported.
- Central 50, 80 and 90 per cent coverage reported.
- Interval widths reported.
- Date-level paired comparisons reported.
- Paired intervals labelled descriptive rather than formal significance tests.
- No model refit performed.
- No model reselection performed.
- No calibration reselection performed.
- Event probabilities not yet calculated.
- Market data not accessed.
- Trading returns not calculated.
- Next task: convert the calibrated distributions into event probabilities.
