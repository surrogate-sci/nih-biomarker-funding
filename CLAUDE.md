# NIH Biomarker Funding Analysis

## Project Goal

Produce data for a policy-level blog post (target venues: Good Science Project, IFP,
Clinical Trial Abundance) supporting or refuting the hypothesis that most NIH biomarker
funding operates without a clear estimand (causal or decision-theoretic), and that
surrogacy/mechanistic validation is an afterthought rather than a design consideration.

The pipeline: keyword-filter 20 years of NIH ExPORTER data into ~270K biomarker grants,
then LLM-grade each on 3 dimensions (biomarker use, research design, evidence strength)
using a custom rubric that extends FDA-NIH BEST to capture the gradient of specificity
in how researchers invoke biomarker concepts.

**Prior art**: The Edison analysis agent (`../edison-benchmarks/`) produced a poor rubric
with ~50% ambiguous classifications. This repo replaces that with a hand-designed rubric.

## Rules

- **RUBRIC.md is scientific content** — do not modify definitions without Manjari's explicit direction
- **"I draft, you correct" workflow** — Manjari dictates scientific substance; Claude organizes/formats
- **`data/` is gitignored** — use `git add -f` for tracked files (RUBRIC.md, calibration CSVs, results)
- **Commit style**: imperative, scoped prefix: `grade: calibrate rubric`, `fetch: add sharder`
- **Don't use**: `_archive/`, `../edison-benchmarks/`, old skill dirs

## Pipeline

### Phase 1: Dataset Curation (complete)

NIH ExPORTER bulk downloads → keyword filtering → unified dataset.

```
process_all_years.py  →  filter_biomarker_projects.py  →  data/filtered/biomarker_FY*.csv
                                                              ↓
                                                       create_unified_dataset.py
                                                              ↓
                                                       nih_biomarker_unified_2004-2024.csv (269,630 grants)
```

- **Term sets**: core (4 terms: biomarker, clinical marker, surrogate endpoint, imaging marker) and expanded (10 terms, adds digital biomarker, endophenotype, genetic marker, etc.)
- `EXPLICIT_BIOMARKER` column flags core-term matches (75,849 grants, $35.77B)
- Data quality: FY2005 PROJECT_TERMS 68% populated; FY2006 PROJECT_TERMS empty
- See `README.md` for full script docs and commands

### Phase 2: LLM Classification (current focus)

3-dimension rubric grading via LLM ensemble.

```
RUBRIC.md → grader_prompt.py (build_system_prompt) → OpenRouter API
                                                      ↓
calibration_examples.csv → run_calibration.py → calibration_results_*.json
```

- **Models**: Gemini 2.5 Flash Lite + GPT-4o-mini (primary), Sonnet 4.6 Batch API (tiebreaker on ~28% disagreements). ~$700-900 for 270K grants.
- **Rubric**: 17 Dim1 (biomarker use) + 10 Dim2 (research design) + 5 Dim3 (evidence strength) codes
- Abstracts from `~/Downloads/RePORTER_PRJABS_C_FY*.zip` (FY2016 missing)

## Key Files

| File | Role |
|------|------|
| `data/RUBRIC.md` | Source of truth: classification rubric with "Assign when..." definitions |
| `scripts/grader_prompt.py` | Loads RUBRIC.md at runtime, constructs system prompt, calls OpenRouter |
| `scripts/run_calibration.py` | Runs grader on calibration examples (`--model`, `--limit`, `--delay`) |
| `scripts/filter_biomarker_projects.py` | Filters NIH ExPORTER CSVs by keyword term sets |
| `scripts/process_all_years.py` | Batch download + filter FY2004-2024 |
| `scripts/create_unified_dataset.py` | Merges filtered year CSVs into single dataset |
| `scripts/generate_summary.py` | Produces `data/filtered/SUMMARY.md` |
| `data/grader_calibration_examples.csv` | 25 easy cases (explicit biomarker terms from 2012 & 2022) |
| `data/nih_biomarker_unified_2004-2024.csv` | 269,630 grants, NO abstracts |

## Commands

```bash
# Phase 1: Data curation
python3 scripts/process_all_years.py --start-year 2004 --end-year 2024 --skip-download --raw-dir ~/Downloads
python3 scripts/create_unified_dataset.py
python3 scripts/generate_summary.py

# Phase 2: LLM grading
python3 scripts/run_calibration.py --model google/gemini-2.5-flash-lite --limit 5
python3 scripts/run_calibration.py --model openai/gpt-4o-mini

# Utilities
ruff check . && ruff format .
python3 scripts/analyze_keywords.py "surrogate endpoint" "intermediate endpoint"
```

## Status

Calibration done (3 models, 25/25 success, 28% Dim1 disagreement).
Next: cleanup PR → batch classifier → hard cases → full run.
See `docs/plans/2026-03-02-calibration-cleanup-scale.md` for detailed plan.
