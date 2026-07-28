# Notebook 15: Final Reproducibility and Release Audit

## Purpose

Notebook 15 certifies the empirical release represented by the
parent commit completed after Notebook 14.

It does not fit a new model, reselect a model, alter calibration,
select a new trading rule or recalculate results using a different
sample.

## Checks performed

The audit verifies:

1. local and remote branch alignment;
2. the complete manifest lineage;
3. every verifiable SHA256 declaration in that lineage;
4. canonical Notebook 00 to Notebook 14 coverage;
5. successful execution of every canonical upstream notebook;
6. absence of stored notebook execution errors;
7. successful execution of the complete repository test suite;
8. an unchanged model, calibration and trading lineage;
9. the tracked-file inventory of the audited parent commit;
10. the Python and package environment used for certification.

## Interpretation

Certification establishes internal reproducibility of the recorded
empirical release. It does not establish executable profitability,
population-level significance, universal model superiority or
market inefficiency.

The implemented weather source remains deterministic IFS with
probabilistic post-processing. The release does not claim an
implemented AIFS ENS, ECMWF ENS or Earth-2 forecast experiment.
