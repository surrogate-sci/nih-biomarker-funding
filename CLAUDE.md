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

**Blocking issue**: LLM grader needs improvement. Previous Kosmos analysis had ~50% ambiguous classifications due to:
1. Binary "Causal vs Correlational" was too simplistic
2. Zero-shot classification had poor reliability
3. Grader prompts lacked scientific rigor

**RUBRIC.md status**: Has basic category structure but marked with `[EXAMPLE NEEDED]`, `[NUANCE]`, `[MATURE JUDGMENT NEEDED]` tags awaiting expert input on:
- Predictive vs Prognostic distinctions
- Correlate vs Surrogate (Fleming's "a correlate does not a surrogate make")
- Level 0 (individual prognosis) vs surrogate endpoint research

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

1. Fill in RUBRIC.md with concrete examples and decision rules
2. Pull "hard cases" for grader testing
3. Design improved grader prompt with few-shot examples
4. Test on calibration examples
5. Re-run classification on full dataset
