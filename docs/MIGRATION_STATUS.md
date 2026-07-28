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

## Locked event probability construction

- Locked calibrated temperature distributions retained.
- Certified eleven-event definitions retained.
- Event partitions checked for gaps and overlaps.
- Lower and upper tails checked.
- Left-closed and right-open boundary convention retained.
- Ninety-nine quantiles treated as deterministic equal-weight particles.
- Every particle assigned to exactly one event.
- Every date-rule probability vector contains eleven events.
- Every probability vector sums to one.
- Probability resolution fixed at one divided by ninety-nine.
- Exact zero probabilities retained.
- Probability regularisation not yet selected.
- Realised outcomes not accessed.
- Categorical scores not calculated.
- Market prices not accessed.
- Trading returns not calculated.
- Next task: development-only selection of uniform probability mixing.

## Notebook 09 probability calibration

- Retained the pooled empirical residual model.
- Retained the continuous dispersion scale of 1.25.
- Used 152 calibrated out-of-fold forecasts over 38 development dates.
- Treated settlement date as the uncertainty unit.
- Used categorical log score as the primary selection criterion.
- Retained multiclass Brier score as a secondary diagnostic.
- Evaluated 101 mixing parameters from 0.00 to 1.00.
- Obtained a strict development winner of 0.02.
- Selected 0.01 using the one-standard-error rule.
- Applied 0.01 unchanged to the holdout and June probability books.
- Did not use holdout or June outcomes for selection.
- Did not access market prices or calculate trading returns.
- Next stage: locked categorical evaluation.

## Notebook 10 locked categorical evaluation

- Joined all 1,749 locked probability rows to certified HKO outcomes.
- Verified the join using event order and certified event index.
- Evaluated 40 holdout and 119 June probability books.
- Treated settlement date as the uncertainty unit.
- Recorded categorical log score as the primary score.
- Recorded multiclass Brier score as the secondary score.
- Found one raw zero probability for a realised June event.
- Confirmed that the locked 0.01 mixture makes every log score finite.
- Recorded only a small Brier-score cost from regularisation.
- Did not reselect any model or calibration component.
- Did not access market prices or calculate trading returns.
- Next stage: common-support market comparison.

## Notebook 11 common-support market comparison

- Status: `COMMON_SUPPORT_MARKET_COMPARISON_COMPLETE`.
- Certified the canonical `18sA` market source.
- Certified `p_market` as the historical market-price field.
- Gave the canonical source precedence over derived copies.
- Retained 154 complete common-support books.
- Evaluated 40 settlement dates.
- Reported 5 model-only books.
- Reported 1 market-only book.
- Normalised market prices only for categorical scoring.
- Preserved raw prices for later trading analysis.
- Used settlement date as the uncertainty unit.
- Did not revisit model selection or calibration.
- Did not calculate trading returns.

## Notebook 12 locked trading strategy

- Status: `TRADING_STRATEGY_LOCKED_AND_EVALUATED`.
- Used 29 balanced development dates.
- Compared all four decision rules on identical date support.
- Used raw market prices rather than categorical normalisation.
- Selected `24h_prior__tau_0.075`.
- Locked decision rule: `24h_prior`.
- Locked edge threshold: `0.075`.
- Permitted at most one long-YES position per settlement date.
- Kept the weather model and both calibration stages unchanged.
- Did not use holdout or June outcomes for strategy selection.
- Did not refit the strategy before the June external block.
- Evaluated the holdout and June blocks separately.
- Added fixed-cost sensitivity without reselection.
- Retained reduced-form rather than executable-profitability claims.

## Notebook 13 date-level uncertainty analysis

- Status: `DATE_LEVEL_UNCERTAINTY_ANALYSIS_COMPLETE`.
- Used settlement date as the uncertainty unit.
- Evaluated 6 distinct estimands.
- Used 20000 fixed-seed date-bootstrap repetitions.
- Used exact sign flips for blocks with at most
  20 dates.
- Used fixed-seed Monte Carlo sign flips for larger blocks.
- Kept the weather model unchanged.
- Kept continuous calibration unchanged.
- Kept probability calibration unchanged.
- Kept the trading strategy unchanged.
- Did not refit before the June external block.
- Reported holdout and June uncertainty separately.
- Treated all inference as descriptive finite-sample evidence.
- Made no executable-profitability or market-inefficiency claim.

## Notebook 14: Final Empirical Synthesis

Status: complete.

The locked results from Notebooks 04 to 13 have been consolidated
into a single numerical evidence register and a claim-boundary
table. No model, calibration parameter or trading strategy was
reselected. The next empirical stage is the final reproducibility
and release audit.

## Notebook 15: Reproducibility Release Audit

Status: complete.

The empirical parent commit has been audited for manifest lineage,
hash consistency, canonical notebook execution, branch alignment,
test completion and preservation of all locked choices. The next
stage is thesis table extraction and final empirical reporting.

## Notebook 16: Thesis Evidence

Status: complete.

The certified empirical release has been converted into compact CSV
tables, LaTeX tables, figures, a numerical results register and a
claim-boundary register. No model, calibration parameter or trading
strategy was changed.

The empirical implementation is ready for integration into the
dissertation Results, Discussion and Appendix chapters.
