# Phase 21 Clean-Environment Reproducibility Demonstration

## Status

PASSED

## Purpose

Phase 21 tests whether the completed Gaussian-process empirical programme can be regenerated from the tracked repository state rather than accepted from previously saved outputs. A fresh local Git clone was created at the certified Phase 20 commit. Generated Phase 15-20 artifacts were removed inside that clone, and all six engines and their phase-specific tests were rerun in chronological order.

## Isolation boundary

- Fresh filesystem state: a new local Git clone containing only tracked files.
- Separate interpreter state: a new virtual environment.
- Controlled process state: `PYTHONHASHSEED=0`, `TZ=UTC`, `LC_ALL=C` and `MPLBACKEND=Agg`.
- Offline replay: no API or network retrieval was performed.
- The original certified repository outputs were not modified during replay.

The virtual environment inherits the installed scientific package stack through `--system-site-packages`, because the replay must work offline. Core package versions are matched exactly and `pip check` must pass. This is therefore a clean repository and interpreter replay, not a claim that a completely new machine can install packages without access to a package index.

## Replay coverage

| Phase | Regenerated artifacts | Maximum finite comparison error | Status |
|---|---:|---:|---|
| 15 | 10 | 0.000e+00 | PASSED |
| 16 | 10 | 0.000e+00 | PASSED |
| 17 | 17 | 0.000e+00 | PASSED |
| 18 | 21 | 0.000e+00 | PASSED |
| 19 | 29 | 0.000e+00 | PASSED |
| 20 | 29 | 0.000e+00 | PASSED |

- Total artifacts compared: 116.
- CSV files were compared by dimensions, columns, row order and values.
- JSON files were compared after removing only dynamic provenance fields.
- Markdown and text files were compared after path, timestamp and line-ending normalisation.
- PNG figures were compared as pixel arrays.
- PDF figures were required to regenerate as non-empty files.

## Dependency and provenance audit

- Critical tracked source files hashed: 18.
- Seed and random-state evidence rows: 85.
- Core package versions matched: 6 of 6.
- `pip check`: PASSED.
- Exact direct-package pins: `requirements-v2-completion.txt`.
- Conda environment description: `environment-v2-completion.yml`.

## Reproduction command

```bash
bash tools/v2_completion/reproduce_v2_completion.sh
```

## Interpretation

The code-to-mathematics reconciliation, static benchmark, deterministic-error and missing-support analysis, rule and block GP diagnostics, predictive diagnostics, forecast combination, and GP-market discrepancy results can all be regenerated from the submitted tracked state. The reported tables and figures are therefore code-generated rather than manually edited.

## Closed Phase 14 gap

- G15: clean-environment reproducibility.

## Evidential boundary

The clean replay begins from the frozen tracked Phase 20 state and reruns Phases 15-20. It does not repeat historical external API acquisition from Phases 1-4, because provider archives and endpoints may change. The tracked and hashed forecast, settlement and market panels therefore constitute the frozen numerical inputs. Fresh dependency installation on another machine remains governed by the pinned requirements and environment files.
