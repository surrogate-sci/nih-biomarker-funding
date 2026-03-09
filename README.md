# Project Goals

How much money has been spent on different parts of biomarker research (technology development, clinical biomarker discovery, biomarker translation,  clinical validation (however that is operationalized). Eventually some biomarkers are evaluated by regulatory agencies or by the medical decision making community for effectiveness. 


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
- `--term-set core`: 4 explicit biomarker terms (biomarker, clinical marker, surrogate endpoint, imaging marker)
- `--term-set expanded`: 10 terms including digital biomarker, endophenotype, genetic marker, clinical+omics, clinical+imaging

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

### Analysis & Visualization Scripts

**5. Create HTML Visualizations** (`scripts/create_html_charts.py`)

Generates interactive HTML charts using Chart.js for biomarker funding trends:

```bash
python3 scripts/create_html_charts.py
```

**Output:** Standalone HTML files in `visualizations/` directory showing funding by year and by institute for different biomarker categories.

**6. Analyze Keywords** (`scripts/analyze_keywords.py`)

Search the unified dataset for specific keywords and generate statistics:

```bash
# Single keyword
python3 scripts/analyze_keywords.py "biomarker discovery"

# Multiple keywords (OR search)
python3 scripts/analyze_keywords.py "surrogate endpoint" "intermediate endpoint"
```

**Output:** Statistics (funding by year, top institutes) and filtered CSV file.

### LLM Classification Scripts

**7. Grader Prompt Library** (`scripts/grader_prompt.py`)

Library module that loads `data/RUBRIC.md`, constructs system prompts, and provides the OpenRouter API helper. Imported by `run_calibration.py` and future batch scripts.

**8. Run Calibration** (`scripts/run_calibration.py`)

Runs the grader on calibration examples to validate model behavior:

```bash
python3 scripts/run_calibration.py --model google/gemini-2.5-flash-lite --limit 5
python3 scripts/run_calibration.py --model openai/gpt-4o-mini
```

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

**Current Dataset**: `data/nih_biomarker_unified_2004-2024.csv`
- 269,630 unique project-year records (Application ID + Fiscal Year combinations)
- Spans FY2004 - FY2024 (21 years)
- Unified dataset with selected columns (removes large text fields like PROJECT_TERMS)
- Sourced from NIH ExPORTER bulk data filtered by biomarker-related keywords

**Individual Year Files**: `data/filtered/biomarker_FY{year}.csv`
- One CSV per fiscal year (2004-2024)
- Each includes `EXPLICIT_BIOMARKER` column flagging core term matches
- Full project data including abstracts and metadata

**Summary Statistics** (from `data/filtered/SUMMARY.md`):
- **Total Matched Projects**: 269,630 (16.9% of scanned projects)
- **Explicit Biomarker Projects**: 75,849 (4.8% of scanned projects)
- **Total Biomarker Relevant Spending**: $134.49B
- **Explicit Biomarker Spending**: $35.77B (26.6% of total)

**Search Terms Used**:
- **Core terms (4)**: biomarker, clinical marker, surrogate endpoint, imaging marker
- **Expanded terms (10)**: core + digital biomarker, intermediate outcome, endophenotype, genetic marker, clinical+omics, clinical+imaging

**Data Quality Notes**:
- FY2005: PROJECT_TERMS field only 68% populated (vs 89% in FY2004)
- FY2006: PROJECT_TERMS field completely empty (0% populated)
- These years show artificially low match counts since filtering relies heavily on PROJECT_TERMS keywords


## Results

For current summary statistics and per-year funding breakdowns, see `data/filtered/SUMMARY.md`.

**Key Findings** (FY2004-2024):
- Biomarker-related research represents 16.9% of all NIH projects scanned
- Total biomarker relevant spending: $134.49B over 21 years
- Explicit biomarker projects (core terms) account for 4.8% of projects and $35.77B in funding
- Strong growth trend: funding increased from $1.71B (FY2004) to $13.55B (FY2024)
- Peak year: FY2024 with 23,252 matched projects and $13.55B in biomarker relevant spending

**Classification Rubric**: `data/RUBRIC.md`
- Source of truth for the 3-dimension classification scheme
- 17 Dimension 1 codes (biomarker use), 10 Dimension 2 codes (research design), 5 Dimension 3 codes (evidence strength)
- Loaded at runtime by `scripts/grader_prompt.py`