# Project Goals

The goal of this analysis to answer how much money has been spent on different parts of biomarker research, and whether that is aligned with the scientific needs of each biomarker context of use The scope of analysis includes technology development, clinical biomarker discovery, biomarker translation,  clinical validation (however that is operationalized). Eventually some biomarkers are evaluated by regulatory agencies or by the medical decision making community for effectiveness. 


## Purpose of the repository

This code repository analyzes NIH biomarker research funding using LLM-based classification to understand spending patterns across different research phases and contexts of use. The code uses broad keyword filters to create manageable datasets from NIH Reporter exports, then employs LLM graders to classify projects into specific research categories. 


The workflow is:
- Start with NIH Reporter exports filtered by broad biomarker-related keywords (biomarker validation, surrogate endpoints, etc.)

- Combine and deduplicate multiple searches to create a unified dataset

- Classify each project into biomarker phases of interest: technology development, biomarker discovery, biomarker validation, and occasionally biomarker qualification for regulatory approval. However, biomarker research is more complicated than that, so we will also dig into research funding given to different biomarker contexts of use such as diagnostics, clinical trial enrichment, or surrogate endpoints. 

- For complicated classification of project abstracts, use an LLM grader with a documented rubric and prompts;

- Perform user specified aggregation of the data. Potentially by research phase, NIH institute, funding mechanism, and year.  

- Export analysis tables and small artifacts for review.

- (optional) Build a dashboard that can be hosted on gradio to view existing dataset.


## Scripts

### Core Workflow Scripts

**1. Filter NIH ExPORTER Data** (`scripts/filter_biomarker_projects.py`)

Filter individual fiscal year data for biomarker-related projects. This is the core filtering script that searches for biomarker terms in project titles and terms.

```bash
# Filter a single year
python3 scripts/filter_biomarker_projects.py \
  --input-csv ~/Downloads/RePORTER_PRJ_C_FY2024.csv \
  --output data/filtered/biomarker_FY2024.csv \
  --term-set expanded
```

**Search term sets:**
- `--term-set core`: 13 definite biomarker terms (biomarker, clinical marker, surrogate endpoint, imaging marker, endophenotype, intermediate outcome/endpoint, digital endpoint, risk stratification, patient selection, companion diagnostic, predicting response, response to therapy)
- `--term-set expanded`: 36 terms (all core + diagnostics, stratification, precision medicine, and signature terms)

**Facility screening:** Infrastructure sub-projects (Administrative Core, Shared Resource, etc.) are excluded by title pattern. Center grants (P30, P50) are preserved.

**Output:** Adds `EXPLICIT_BIOMARKER` column (TRUE/FALSE) to flag projects matching core terms. Deduplicates by (APPLICATION_ID, FY) to preserve yearly funding records.

**2. Batch Process Multiple Years** (`scripts/process_all_years.py`)

Automates downloading, extracting, and filtering multiple fiscal years from NIH ExPORTER:

```bash
# Process years 2004-2024 with existing downloads
python3 scripts/process_all_years.py \
  --start-year 2004 \
  --end-year 2024 \
  --skip-download \
  --raw-dir ~/Downloads \
  --term-set expanded

# Download and process years automatically
python3 scripts/process_all_years.py \
  --start-year 2004 \
  --end-year 2024 \
  --term-set expanded
```

**Output:** Individual year CSVs in `data/filtered/biomarker_FY{year}.csv`

**3. Generate Summary Report** (`scripts/generate_summary.py`)

Create summary report from already-filtered data (lightweight - no reprocessing):

```bash
# Generate summary from data/filtered/
python3 scripts/generate_summary.py

# Use custom directory
python3 scripts/generate_summary.py --filtered-dir path/to/filtered/
```

**Output:** `data/filtered/SUMMARY.md` with:
- Per-year funding and project counts
- Biomarker relevant spending vs explicit biomarker spending
- Overall statistics and data quality notes

**4. Create Unified Dataset** (`scripts/create_unified_dataset.py`)

Combines all filtered year files into a single unified dataset with selected columns (removes large text fields to reduce file size):

```bash
python3 scripts/create_unified_dataset.py
```

**Output:** `data/nih_biomarker_unified_2004-2024.csv` - single CSV with all years, keeping only analytically useful columns.

### LLM Classification Scripts

**5. Sample Oncology Grants** (`scripts/sample_oncology.py`)

Stratified sample of NCI grants with abstract join from RePORTER zip files:

```bash
python3 scripts/sample_oncology.py \
  --unified data/nih_biomarker_unified_2004-2024.csv \
  --abs-dir ~/Downloads \
  --n 100 --seed 42
```

**Output:** `data/oncology_sample_100per_year.csv` (~1,900 grants with abstracts)

**6. LLM Grading via Inspect AI** (`inspect_task.py`) — **recommended**

Single entry point that replaces `run_batch_grading.py` and `run_calibration.py`. Built on [UK AISI Inspect AI](https://inspect.aisi.org.uk/) for structured logging, multi-model comparison, and batch API support.

```bash
# Calibration (25 examples, quick turnaround via OpenRouter)
inspect eval inspect_task.py --model openrouter/google/gemini-2.5-flash-lite --temperature 0.0 --limit 25

# Mid-scale grading (direct provider API)
inspect eval inspect_task.py \
  --model google/gemini-2.5-flash-lite \
  --temperature 0.0 --max-connections 20

# Multi-model comparison
inspect eval-set inspect_task.py \
  --model openai/gpt-4.1-mini,google/gemini-2.5-flash-lite --log-dir logs/

# Production run with batch API (50% cost savings)
inspect eval-set inspect_task.py \
  --model openai/gpt-4.1-mini,google/gemini-2.5-flash-lite \
  --batch --log-dir logs/production-v1

# Browse results in web UI
inspect view
```

**Features:**
- Code enums parsed from `data/RUBRIC.md` at runtime — rubric edits auto-propagate
- `temperature`, `max_tokens` controlled via CLI (not hardcoded)
- Gold-label support: add `GOLD_DIM1/DIM2/DIM3` columns to CSV for expert-label scoring
- `.eval` structured logs for post-hoc analysis with HiBayES, CJE, or custom scripts

**Output:** `.eval` log files in `logs/` with per-grant classifications, model outputs, and scorer metadata. View with `inspect view`.

**6a. Batch LLM Grading** (`scripts/run_batch_grading.py`) — **legacy, being replaced**

Grade grants using LLM ensemble with checkpoint/resume:

```bash
python3 scripts/run_batch_grading.py \
  --sample data/oncology_sample_100per_year.csv \
  --model google/gemini-2.5-flash-lite \
  --output data/oncology_grades_gemini-2.5-flash-lite.jsonl
```

**Output:** JSONL with per-grant classifications on 3 dimensions. Supports `--limit` for smoke tests, resume on restart.

**7. Expert Review** (`scripts/generate_review.py`)

Generate standalone HTML for expert grading with anti-anchoring design:

```bash
python3 scripts/generate_review.py \
  --examples data/grader_calibration_examples.csv \
  --results-dir data/
```

**Output:** `data/expert_review.html` — expert grades before seeing model outputs, localStorage persistence, CSV export.

**8. Agreement Analysis** (`scripts/analyze_agreement.py`, `scripts/extract_disagreements.py`)

Analyze inter-model agreement and extract disagreement patterns:

```bash
python3 scripts/analyze_agreement.py --data-dir data/
python3 scripts/extract_disagreements.py --data-dir data/
```

### Analysis & Visualization Scripts

**9. Create HTML Visualizations** (`scripts/create_html_charts.py`)

Generates interactive HTML charts using Chart.js for biomarker funding trends:

```bash
python3 scripts/create_html_charts.py --input-dir data/oct-2024 --output-dir visualizations/
```

**Output:** Standalone HTML files in `visualizations/` directory showing funding by year and by institute for different biomarker categories.

**10. Analyze Keywords** (`scripts/analyze_keywords.py`)

Search the unified dataset for specific keywords and generate statistics:

```bash
python3 scripts/analyze_keywords.py --input data/nih_biomarker_unified_2004-2024.csv "surrogate endpoint" "intermediate endpoint"
```

**Output:** Statistics (funding by year, top institutes) and filtered CSV file.

**Note on Legacy Scripts**:
- `scripts/nih_bulk_downloader.py` - Outdated bulk downloader. Use `process_all_years.py` for current workflow.
- `scripts/dedupe_and_union.py` - Used for the October 2024 dataset (`data/oct-2024/`). For FY2004-2024 workflow, use `create_unified_dataset.py`.

### Workflow

**Standard workflow:**

1. **Download & Filter** (heavy processing, run once): 
   ```bash
   python3 scripts/process_all_years.py --start-year 2004 --end-year 2024
   ```
   Downloads NIH ExPORTER ZIP files, extracts CSVs, and filters for biomarker projects. Outputs individual year files to `data/filtered/`.

2. **Generate Summary** (lightweight reporting, run anytime):
   ```bash
   python3 scripts/generate_summary.py
   ```
   Creates `data/filtered/SUMMARY.md` with funding statistics and project counts.

3. **Create Unified Dataset** (combine years):
   ```bash
   python3 scripts/create_unified_dataset.py
   ```
   Combines all filtered years into `data/nih_biomarker_unified_2004-2024.csv` for analysis.

4. **Visualize & Analyze** (optional):
   ```bash
   python3 scripts/create_html_charts.py  # Generate charts
   python3 scripts/analyze_keywords.py "keyword"  # Search dataset
   ```


## Data

**Downloads**:
- [GitHub Release (v3.0)](https://github.com/surrogate-sci/nih-biomarker-funding/releases/download/dataset-release-v3.0/nih_biomarker_unified_2004-2024.zip) — 39MB zip (expanded keywords + facility screening, 344K grants)
- [GitHub Release (v2.0)](https://github.com/surrogate-sci/nih-biomarker-funding/releases/download/dataset-release-v2.0/nih_biomarker_unified_2004-2024.zip) — 38MB zip (keyword + abstract union, 332K grants)
- [GitHub Release (v1.0)](https://github.com/surrogate-sci/nih-biomarker-funding/releases/download/dataset-release-v1.0/nih_biomarker_unified_2004-2024.zip) — 130MB zip (keywords only, 270K grants)
- [Google Drive](https://drive.google.com/file/d/1izm9E7S2KFZSeVcRbD40n-BWVEz9oIPS/view?usp=drivesdk) — v1.0

**Current Dataset**: `data/nih_biomarker_unified_2004-2024.csv`
- 344,550 unique project-year records (union of keyword + abstract text filters)
- Spans FY2004 - FY2024 (21 years)
- Sourced from NIH ExPORTER bulk data filtered by biomarker-related keywords in PROJECT_TITLE, PROJECT_TERMS, and ABSTRACT_TEXT

**Per-grant columns**:

| Column | Description |
|--------|-------------|
| `MATCH_SOURCE` | `keywords_only` or `abstract_only` — where the keyword matched |
| `MATCHED_TERMS` | Semicolon-delimited list of all matching terms |
| `PRIMARY_TERM` | Single most-specific term per grant (non-overlapping) |
| `EXPLICIT_BIOMARKER` | TRUE if any core (13) term matched |

**Individual Year Files**:

```
data/filtered/
  keywords/biomarker_FY{year}.csv          # keyword matches (PROJECT_TITLE + PROJECT_TERMS)
  abstracts/biomarker_abstract_FY{year}.csv # abstract-only matches (ABSTRACT_TEXT)
  SUMMARY.md                                # unified comparison
```

**Summary Statistics** (from `data/filtered/SUMMARY.md`):
- **Total Matched Projects**: 344,550 (keywords: 276,161 + abstract-only: 68,389)
- **Core Biomarker Term Matches (EXPLICIT_BIOMARKER=TRUE)**: 127,394
- **Total Biomarker Relevant Spending**: $175.2B

**Search Terms Used**:
- **Core terms (13)**: biomarker, clinical marker, surrogate endpoint, imaging marker, endophenotype, intermediate outcome, intermediate endpoint, digital endpoint, risk stratification, patient selection, companion diagnostic, predicting response, response to therapy
- **Expanded terms (36)**: core + digital biomarker, genetic marker, clinical+omics, clinical+imaging, diagnostic accuracy/sensitivity/specificity, clinical diagnostics, personalized diagnostics, clinical predictors, prognostic value/assays, clinically actionable, patient/disease stratification, disease heterogeneity, clinical subtypes, theranostics, precision oncology, predictive/genomic/proteomic signature, biosignature

**Data Quality Notes**:
- FY2005-06 and FY2013/2018 had sparse PROJECT_TERMS — now mitigated by abstract text search
- See `data/filtered/SUMMARY.md` for per-year breakdowns by filter method


## Results

For current summary statistics and per-year funding breakdowns, see `data/filtered/SUMMARY.md`.

**Key Findings** (FY2004-2024, unified dataset v3.0):
- 344,550 biomarker-related grants totaling $175.2B over 21 years
- 20% of grants (68,389) were only discoverable via abstract text search
- 37% of grants (127,394) match core biomarker terms (EXPLICIT_BIOMARKER=TRUE)
- Sparse years (FY2005-06, FY2013, FY2018) recovered via abstract search
- NCI (CA) accounts for 84K grants; NIEHS (ES) has highest explicit-biomarker rate (69%)

**Oct-2024 Dataset**: 
The `data/oct-2024/` directory contains analysis results from October 2024 using different search strategies and keyword filters. This is a separate analysis from the current FY2004-2024 workflow which uses the expanded term set.