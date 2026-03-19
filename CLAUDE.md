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
- **Manjari edits concurrently in Cursor** — check for file modifications before overwriting; preserve her changes
- **Refactoring/cleanup → PR** (not direct commit to main). Doc updates → direct commit is fine.
- **`data/` is gitignored** — use `git add -f` for tracked files (RUBRIC.md, calibration CSVs, results)
- **Commit style**: imperative, scoped prefix: `grade: calibrate rubric`, `fetch: add sharder`
- **Don't use**: `_archive/`, `../edison-benchmarks/`, old skill dirs
- **Don't invent scientific positions** — never paraphrase domain claims or add causal language Manjari didn't provide

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

- **Models**: Gemini 2.5 Flash Lite + GPT-4.1-mini (primary), Sonnet 4.6 Batch API (tiebreaker on ~28% disagreements). ~$700-900 for 270K grants.
- **Rubric**: 17 Dim1 (biomarker use) + 10 Dim2 (research design) + 5 Dim3 (evidence strength) codes
- Abstracts from `~/Downloads/RePORTER_PRJABS_C_FY*.zip` (FY2016 missing)

## Key Files

| File | Role |
|------|------|
| `data/RUBRIC.md` | Source of truth: classification rubric with "Assign when..." definitions |
| `scripts/grader_prompt.py` | Loads RUBRIC.md at runtime, constructs system prompt, calls OpenRouter/OpenAI |
| `scripts/utils.py` | Shared utilities: `load_env()`, `parse_llm_json()` |
| `scripts/run_calibration.py` | Runs grader on calibration examples (`--model`, `--limit`, `--delay`) |
| `scripts/abstract_loader.py` | Loads abstracts from RePORTER zip files |
| `scripts/sample_oncology.py` | Stratified NCI sample + abstract join |
| `scripts/run_batch_grading.py` | Batch grading with JSONL checkpoint/resume |
| `scripts/generate_review.py` | Expert review HTML generator (anti-anchoring design) |
| `scripts/analyze_agreement.py` | Inter-model agreement analysis |
| `scripts/extract_disagreements.py` | Extract disagreement patterns for rubric refinement |
| `scripts/filter_biomarker_projects.py` | Filters NIH ExPORTER CSVs by keyword term sets |
| `scripts/process_all_years.py` | Batch download + filter FY2004-2024 |
| `scripts/create_unified_dataset.py` | Merges filtered year CSVs into single dataset |
| `data/grader_calibration_examples.csv` | 25 easy cases (explicit biomarker terms from 2012 & 2022) |
| `data/nih_biomarker_unified_2004-2024.csv` | 269,630 grants, NO abstracts |

## Commands

```bash
# Phase 1: Data curation
python3 scripts/process_all_years.py --start-year 2004 --end-year 2024 --skip-download --raw-dir ~/Downloads
python3 scripts/create_unified_dataset.py
python3 scripts/generate_summary.py

# Phase 2: Sampling + LLM grading
python3 scripts/sample_oncology.py --unified data/nih_biomarker_unified_2004-2024.csv --abs-dir ~/Downloads --n 100 --seed 42
python3 scripts/run_batch_grading.py --sample data/oncology_sample_100per_year.csv --model google/gemini-2.5-flash-lite --output data/oncology_grades_gemini-2.5-flash-lite.jsonl
python3 scripts/run_calibration.py --model google/gemini-2.5-flash-lite --limit 5

# Phase 3: Analysis + Expert review
python3 scripts/analyze_agreement.py --data-dir data/
python3 scripts/extract_disagreements.py --data-dir data/
python3 scripts/generate_review.py --examples data/grader_calibration_examples.csv --results-dir data/

# Utilities
ruff check . && ruff format .
python3 -m unittest tests.test_generate_review -v
```

## Status

Scale-up experiment complete: 2,309 Gemini grades on NCI oncology sample.
GPT-4.1-mini and GPT-4o-mini partial (~150-230 grades each).
28% Dim1 three-way disagreement on calibration set.
Open issues: #3-#8 (rubric boundaries, Inspect AI migration, trace storage).
Next: rubric refinement → Inspect AI migration → full 270K run.
