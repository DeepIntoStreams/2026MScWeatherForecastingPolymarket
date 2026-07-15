# 20b date-grouped cross-validation and chronological holdout design

## Purpose

This step freezes the supervised-learning evaluation design before any tree-based model is fitted.
All contracts from the same HKO settlement date remain in the same partition.

## Frozen design

- Total settlement dates: `48`
- Development dates: `38`
- Final chronological holdout dates: `10`
- Final holdout begins: `2026-05-22`
- Final holdout ends: `2026-05-31`
- Expanding-window validation folds: `4`
- Initial minimum training dates: `16`

The final holdout is never used for feature selection, hyperparameter comparison, calibration fitting, or early stopping.

## Final partition summary

| sample_partition   |   n_rows |   n_dates |   n_positive |   outcome_rate | first_date   | last_date   |
|:-------------------|---------:|----------:|-------------:|---------------:|:-------------|:------------|
| development        |     1535 |        38 |          141 |      0.0918567 | 2026-04-10   | 2026-05-21  |
| final_holdout      |      440 |        10 |           40 |      0.0909091 | 2026-05-22   | 2026-05-31  |

## Cross-validation fold summary

|   cv_fold | cv_role    |   n_rows |   n_dates |   n_positive |   outcome_rate | first_date   | last_date   |   12h_prior |   24h_prior |   6h_prior |   event_day_open |
|----------:|:-----------|---------:|----------:|-------------:|---------------:|:-------------|:------------|------------:|------------:|-----------:|-----------------:|
|         1 | train      |      600 |        16 |           56 |      0.0933333 | 2026-04-10   | 2026-04-25  |         142 |         151 |        131 |              176 |
|         1 | validation |      253 |         6 |           23 |      0.0909091 | 2026-04-26   | 2026-05-01  |          66 |          55 |         66 |               66 |
|         2 | train      |      853 |        22 |           79 |      0.0926143 | 2026-04-10   | 2026-05-01  |         208 |         206 |        197 |              242 |
|         2 | validation |      253 |         6 |           23 |      0.0909091 | 2026-05-02   | 2026-05-07  |          66 |          55 |         66 |               66 |
|         3 | train      |     1106 |        28 |          102 |      0.0922242 | 2026-04-10   | 2026-05-07  |         274 |         261 |        263 |              308 |
|         3 | validation |      220 |         5 |           20 |      0.0909091 | 2026-05-08   | 2026-05-12  |          55 |          55 |         55 |               55 |
|         4 | train      |     1326 |        33 |          122 |      0.092006  | 2026-04-10   | 2026-05-12  |         329 |         316 |        318 |              363 |
|         4 | validation |      209 |         5 |           19 |      0.0909091 | 2026-05-13   | 2026-05-21  |          55 |          44 |         55 |               55 |

## Integrity checks

| check                                         | passed   | detail                                               |
|:----------------------------------------------|:---------|:-----------------------------------------------------|
| matrix_nonempty                               | True     | rows=1975                                            |
| unique_date_group_mapping                     | True     | dates=48, groups=48                                  |
| holdout_nonempty                              | True     | holdout_dates=10                                     |
| holdout_strictly_after_development            | True     | development_end=2026-05-21, holdout_start=2026-05-22 |
| minimum_development_dates                     | True     | development_dates=38, minimum=16                     |
| all_rows_assigned                             | True     | missing=0                                            |
| no_date_split_between_development_and_holdout | True     | each date has one final partition                    |
| cv_fold_count                                 | True     | folds=4                                              |
| cv_train_precedes_validation                  | True     | violating_folds=0                                    |
| cv_train_validation_disjoint                  | True     | overlap_dates=0                                      |
| each_post_initial_date_validated_once         | True     | validated_dates=22                                   |
| holdout_excluded_from_cv                      | True     | final holdout dates do not appear in CV assignments  |
| binary_target_valid                           | True     | bad=0                                                |
| holdout_contains_event_types                  | True     | event_types=3                                        |

## Interpretation

The effective independent sample size is the number of settlement dates rather than the number of contract rows. The expanding-window design preserves chronology and prevents contracts from the same daily event book from being split across training and validation.

## Restrictions for 20c

1. Do not reshuffle rows or dates.
2. Do not inspect final-holdout scores during hyperparameter selection.
3. Fit preprocessing, calibration and class-weight choices using training dates only.
4. Report both contract-level proper scores and date-aggregated paired score differences.
5. Keep tree complexity modest because the development sample contains few independent dates.
