# Environment snapshot

This folder records the environment at final-pipeline initialisation.

`requirements.snapshot.txt` is intentionally a full environment snapshot rather
than the final minimal requirements file.

After the complete pipeline is operational, unused dependencies will be removed and
a minimal reproducible dependency specification will replace it.
