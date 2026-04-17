# Aurora PPT Generator — Configuration

This document lists environment variables used to configure the Strands PPT generator behavior
for image selection and scoring.

These variables are read at module import time by `CG-Backend/lambda/strands_ppt_generator/strands_ppt_generator.py`.

Environment variables

- `AURORA_USE_TFIDF` (bool, default: `1` / enabled)
  - If set to `0`, `false`, `no`, or an empty string the TF-IDF matcher will be skipped and the generator
    will treat TF-IDF as neutral when combining scores.

- `AURORA_TFIDF_WEIGHT` (float, default: `0.6`)
  - Relative weight applied to TF-IDF similarity scores when combining with the legacy heuristic.

- `AURORA_LEGACY_WEIGHT` (float, default: `0.4`)
  - Relative weight applied to the legacy heuristic (simple alt_text matching) when combining with TF-IDF.

- `AURORA_SELECTION_LOG` (string, default: empty / disabled)
  - Path to CSV file for logging image selection decisions. When set, the generator will log all candidate
    images with their scores (TF-IDF, legacy, combined) and mark which one was selected.
  - Example: `export AURORA_SELECTION_LOG=/tmp/selection_log.csv`

- `AURORA_SELECTION_LOG_APPEND` (bool, default: `0` / overwrite)
  - If set to `1`, append to existing telemetry file instead of overwriting.
  - Useful for collecting data across multiple runs.

Notes on weighting and normalization

- The generator normalizes the two weights so they sum to 1.0. Example: if `AURORA_TFIDF_WEIGHT=0.75` and
  `AURORA_LEGACY_WEIGHT=0.25` the effective TF-IDF weight is 0.75 and legacy is 0.25.
- If both weights are set to `0`, the generator falls back to safe defaults: TF-IDF weight `0.6`, legacy `0.4`.
- To completely disable TF-IDF influence, set `AURORA_USE_TFIDF=0` — the code will substitute a neutral TF-IDF score
  so legacy heuristics determine ordering.

Examples

Disable TF-IDF in CI or runtime:

```bash
export AURORA_USE_TFIDF=0
```

Adjust weights to favor TF-IDF strongly:

```bash
export AURORA_TFIDF_WEIGHT=0.8
export AURORA_LEGACY_WEIGHT=0.2
```

Quick troubleshooting tips

- If results seem unexpected, enable more verbose logging for the module logger `aurora.strands_ppt_generator` in your host
  (set it to DEBUG) to see per-candidate scores emitted when the generator runs.
- The generator will log candidate scores (TF-IDF, legacy, combined) for the top few images when the matcher is used.

## What we implemented (so far)

- Environment flags and parsing
  - `AURORA_USE_TFIDF`, `AURORA_TFIDF_WEIGHT`, and `AURORA_LEGACY_WEIGHT` were implemented and are read at module import time by
    `CG-Backend/lambda/strands_ppt_generator/strands_ppt_generator.py`.

- TF-IDF prototype and wiring
  - A lightweight, dependency-free TF-IDF matcher (`image_text_matcher.py`) was added and wired into the generator. The generator
    combines TF-IDF scores with a legacy heuristic using configurable weights.

- Configuration & logging
  - A module-level logger (`aurora.strands_ppt_generator`) was added. The generator emits per-candidate information (tfidf, legacy,
    combined score) which helps tune weights.

- Tests
  - Unit tests added:
    - `tests/test_selection_weights.py` — verifies selection behavior (integration-style)
    - `tests/test_selection_combination.py` — direct unit tests for the selection combination logic and edge cases
  - All tests run locally and are included in the repo test suite.

- CI
  - A GitHub Actions workflow (`.github/workflows/ci.yml`) was added to run tests on push/PR. It now emits a JUnit XML
    (`test-results.xml`) artifact suitable for CI reporting.

## How to verify locally

- Run the full test suite:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q --junitxml=test-results.xml
```

- Temporarily change weights to see different selection behavior. Example (Bash):

```bash
export AURORA_USE_TFIDF=0
export AURORA_TFIDF_WEIGHT=0.2
export AURORA_LEGACY_WEIGHT=0.8
pytest tests/test_selection_weights.py -q
```

- Enable telemetry to collect selection data:

```bash
export AURORA_SELECTION_LOG=/tmp/selection_log.csv
export AURORA_SELECTION_LOG_APPEND=1
pytest tests/test_selection_weights.py -q
# View the log:
cat /tmp/selection_log.csv
```

- Run the integration smoke test to generate a PPTX artifact:

```bash
pytest tests/test_ppt_integration_smoke.py -v
# Check the output:
ls -lh test-output/ci_smoke_test.pptx
```

## Next steps (recommended, prioritized)

1. ✅ **COMPLETED** - Pin development dependencies and add test instructions
   - `requirements-dev.txt` has pinned versions for reproducible environments

2. ✅ **COMPLETED** - Add telemetry/logging for image selection
   - Implemented `selection_telemetry.py` module with CSV logging
   - Controlled by `AURORA_SELECTION_LOG` and `AURORA_SELECTION_LOG_APPEND` env vars
   - Logs all candidates with scores for data-driven weight tuning

3. ✅ **COMPLETED** - Add deterministic tests & CI smoke job
   - Created `tests/test_ppt_integration_smoke.py` for comprehensive smoke testing
   - CI workflow generates PPTX artifact for manual inspection
   - Placeholder detection validated in integration tests

4. Harden CI: add linting and type checks (flake8, mypy) and add JUnit parsing in the Actions checks (medium effort)
   - This prevents regressions and improves code quality over time.

4. Accessibility and metadata (high impact, medium effort)
   - Attach `alt` text and image metadata (caption and machine-friendly alt) to PPTX image shapes for screen readers and export.

5. End-to-end integration tests (S3/http/placeholder) (high effort)
   - Add tests that exercise S3 paths and placeholder flows. Use recorded fixtures or a local S3 emulator in CI to avoid network flakiness.

6. Production tuning and monitoring (ongoing)
   - After collecting telemetry, tune `TFIDF_WEIGHT` vs `LEGACY_WEIGHT` on real data.
   - Consider moving to an embedding-based matcher for semantic accuracy if resources permit.

7. Optional: add a small admin endpoint (or CLI) to run the generator with different env overrides and collect logs for manual inspection.

## Quick contact points & files

- Generator: `CG-Backend/lambda/strands_ppt_generator/strands_ppt_generator.py`
- Matcher prototype: `CG-Backend/lambda/strands_ppt_generator/image_text_matcher.py`
- Tests: `tests/test_selection_weights.py`, `tests/test_selection_combination.py`
- CI: `.github/workflows/ci.yml`
- Docs: `docs/CONFIG.md` (this file)

If you'd like, I can implement any of the prioritized next steps; I recommend starting with pinning dependencies and adding telemetry so you can make data-driven weight adjustments.
