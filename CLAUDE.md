# NIH Biomarker Funding Analysis

## Project Goal
Analyze NIH biomarker funding (2004-2024) to quantify funding for correlative/prognostic biomarkers (Level 0) vs mechanistically valid/surrogate endpoint research (higher causal levels), broken down by institute, grant type, and time.

## Key Data Locations

| What | Where | Notes |
|------|-------|-------|
| Main dataset | `data/nih_biomarker_unified_2004-2024.csv` | 269,630 grants, NO abstracts |
| Project abstracts | `~/Downloads/RePORTER_PRJABS_C_FY*.zip` | NOT in repo; **FY2016 missing**, all others present |
| Calibration examples | `data/grader_calibration_examples.csv` | 25 examples from 2012 & 2022 |
| 2012 examples | `data/grader_examples_2012.csv` | Larger set of 2012 examples |
| Rubric | `data/RUBRIC.md` | Classification rubric, needs expert input |

## Previous Work (OUTDATED - Do Not Use)

- `../edison-benchmarks/data/nih_funding/` - Kosmos analysis with ~50% "ambiguous" classifications
- `nih-reporter-skill/` and `nih-reporter-skill-v2/` - Old skill directories, ignore

## Current Status

**RUBRIC.md** (v2, 2026-03-02): Rewritten with operationalizable "Assign when..." definitions for all 32 codes (17 Dim1, 10 Dim2, 5 Dim3). Source of truth for classification.

**grader_prompt.py**: Refactored to load RUBRIC.md at runtime. Old hardcoded prompt preserved as `_LEGACY_SYSTEM_PROMPT`.

**Pipeline design doc**: `docs/plans/2026-03-02-rubric-grader-pipeline-design.md`

## Calibration Examples

25 examples in `data/grader_calibration_examples.csv` with explicit biomarker terminology:
- surrogate biomarker (9), pharmacodynamic biomarker (4), intermediate biomarker (4)
- surrogate endpoint (4), intermediate endpoint (3), prognostic biomarker (1)

These are "easy cases" - need "hard cases" (grants doing biomarker work without explicit terms) to test grader robustness.

## Key Literature for Rubric

- Fleming & Powers 2012 - 4-level endpoint hierarchy for surrogate endpoints
- Altar et al. 2008 - Evidence map (Grade D→A, higher = more causal)
- IOM/NASEM 2010 - 3-step evaluation framework

## Next Steps

1. ~~Rewrite RUBRIC.md definitions~~ (done)
2. ~~Refactor grader_prompt.py to load RUBRIC.md at runtime~~ (done)
3. Calibration testing on 25 easy cases
4. Sample and label hard cases (grants without explicit biomarker terms)
5. Full dataset classification (~270K grants)

## Gotchas

- `data/` is gitignored — use `git add -f` for files that need tracking (RUBRIC.md, calibration CSVs)
- Old skill dirs archived to `_archive/` — do not use
- RUBRIC.md is a scientific document — do not modify classification definitions without Manjari's direction
- `grader_prompt.py` legacy prompt preserved as `_LEGACY_SYSTEM_PROMPT` for reference only
