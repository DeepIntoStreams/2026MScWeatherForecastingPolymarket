# Final trading contrast extension status

Status: **FINAL RELEASE CANDIDATE — EMPIRICALLY CLOSED**

The original March-August 102-step empirical release remains unchanged.

The extension adds only one pre-specified exploratory contrast: the certified conservative fixed policy versus TAEC-11, a two-sided multi-contract pre-event-exit strategy.

Stages:

- Stage 1: preregistration and feasibility — complete
- Stage 2: four-model probability / trading ledgers — complete
- Stage 2 provenance repair: explicit RBF reconstruction — complete
- Stage 3: performance, risk and Greek-like sensitivity — complete
- Stage 4: dependence-aware inference and multiplicity control — complete
- Stage 4 presentation repair — complete
- Stage 5: robustness and execution reality checks — complete
- Stage 6: thesis pruning, reproducibility and release closure — complete

No new empirical model, threshold, strategy or selection rule is permitted after Stage 6.


Reproducibility note: the clean-clone launcher reconstructs the pre-Stage-2 generated-output state before replay so repository-aware Stage-2 schema discovery cannot read its own later outputs. This is a release-engineering safeguard only and changes no empirical specification.


Canonical-output note: Stage 2-5 committed artefacts were regenerated once from the clean pre-Stage-2 output state and reconciled against the previous release at 1e-10 tolerance for all headline scientific quantities. This canonicalisation changes output generation state only, not the empirical specification or thesis conclusions.

Final manifest-scope note: the scientific-equivalence comparison is a Stage-6 closure audit and is stored outside the Stage-2-to-Stage-5 replay surface. This changes no empirical result or specification.

Final clean-clone canonicalisation: the committed Stage 2-5 artefacts were generated inside a fresh Git clone after two independent clean clones were shown to reproduce identical semantic outputs. Headline scientific quantities were reconciled to the preceding release at 1e-10 tolerance. No empirical specification changed.

Final audit-contract note: reproducibility now distinguishes Git-tracked release artefacts from deterministic generated-but-ignored `.csv.gz` files. The latter are verified against a clean-replay semantic manifest rather than incorrectly required to exist in a fresh clone before replay. No empirical specification or result changed.
