# NIH Biomarker Funding Analysis

Quantifying how the NIH allocates funding across different phases and contexts of biomarker research, and whether that funding reflects clear causal or decision-theoretic frameworks for biomarker evaluation.

This repository builds a classification pipeline over 21 years of NIH ExPORTER data (FY2004-2024), identifying 332,000+ biomarker-related grants and classifying each on three dimensions: biomarker context of use, research design, and strength of evidence for clinical utility.

## Pipeline Overview

```
Phase 1: Data Curation (complete)
  NIH ExPORTER bulk CSVs
    → keyword filtering (PROJECT_TITLE, PROJECT_TERMS)
    → abstract text search (ABSTRACT_TEXT)
    → union + deduplication
    → unified dataset (332,324 grants, $168B)

Phase 2: LLM Classification (active)
  Custom rubric (data/RUBRIC.md)
    → Inspect AI evaluation task
    → multi-model grading (Gemini 2.5 Flash Lite, GPT-4.1-mini)
    → inter-model agreement analysis
    → expert review for rubric refinement

Phase 3: Analysis (planned)
  Classified grants
    → funding patterns by phase, institute, mechanism, year
    → descriptive analysis and visualizations
```

## Quick Start

**Download the dataset:**

```bash
bash scripts/download-dataset.sh   # downloads v2.0 from GitHub Releases
```

Or manually: [v2.0](https://github.com/surrogate-sci/nih-biomarker-funding/releases/download/dataset-release-v2.0/nih_biomarker_unified_2004-2024.zip) (38MB, 332K grants) | [v1.0](https://github.com/surrogate-sci/nih-biomarker-funding/releases/download/dataset-release-v1.0/nih_biomarker_unified_2004-2024.zip) (130MB, 270K grants)

**Set up environment:**

```bash
pip install -r requirements.txt
# For LLM grading, set API keys:
#   OPENROUTER_API_KEY  (OpenRouter)
#   OPENAI_API_KEY      (OpenAI direct)
```

**Run LLM grading (Inspect AI):**

```bash
inspect eval inspect_task.py --model openrouter/google/gemini-2.5-flash-lite --temperature 0.0
inspect view   # browse results
```

## Key Scripts

### Data Curation

| Script | Purpose |
|--------|---------|
| `scripts/filter_biomarker_projects.py` | Filter NIH ExPORTER CSVs by biomarker keyword term sets |
| `scripts/process_all_years.py` | Batch download + filter FY2004-2024 |
| `scripts/create_unified_dataset.py` | Merge filtered year CSVs into single dataset |
| `scripts/supplement_with_abstracts.py` | Add abstract-text matches to keyword-filtered data |
| `scripts/keyword_terms.py` | Centralized keyword term definitions and matching logic |
| `scripts/generate_summary.py` | Generate `data/filtered/SUMMARY.md` statistics |

### LLM Classification

| Script | Purpose |
|--------|---------|
| `inspect_task.py` | Inspect AI evaluation task for rubric-based grading |
| `scripts/sample_oncology.py` | Stratified NCI sample with abstract join |
| `scripts/sample_grants.py` | General-purpose stratified sampler for multi-IC pilots |
| `scripts/generate_review.py` | Expert review HTML generator (anti-anchoring design) |
| `scripts/analyze_agreement.py` | Inter-model agreement analysis |
| `scripts/extract_disagreements.py` | Extract disagreement patterns for rubric refinement |
| `data/RUBRIC.md` | Classification rubric (source of truth) |

### Analysis

| Script | Purpose |
|--------|---------|
| `analysis/biomarker-screening/analyze.py` | Descriptive funding analysis with charts |
| `scripts/plot_funding_overview.py` | Static funding visualizations |

## Data

**Unified dataset:** `data/nih_biomarker_unified_2004-2024.csv`
- 332,324 unique project-year records (FY2004-2024)
- Union of keyword matches (PROJECT_TITLE + PROJECT_TERMS) and abstract text matches

| Column | Description |
|--------|-------------|
| `MATCH_SOURCE` | `keywords_only` or `abstract_only` — where the keyword matched |
| `MATCHED_TERMS` | Semicolon-delimited list of all matching terms |
| `PRIMARY_TERM` | Single most-specific term per grant |
| `EXPLICIT_BIOMARKER` | TRUE if any of the 4 core biomarker terms matched |

**Search terms:**
- **Core (4):** biomarker, clinical marker, surrogate endpoint, imaging marker
- **Expanded (10):** core + digital biomarker, intermediate outcome, endophenotype, genetic marker, clinical+omics, clinical+imaging

**Per-year files:**

```
data/filtered/
  keywords/biomarker_FY{year}.csv          # keyword matches
  abstracts/biomarker_abstract_FY{year}.csv # abstract-only matches
  SUMMARY.md                                # statistics
```

## Development

```bash
ruff check . && ruff format .       # lint and format
python -m pytest tests/ -v          # run tests
```

## Documentation

- `CLAUDE.md` — development conventions and pipeline details
- `data/RUBRIC.md` — classification rubric with dimension definitions
- `docs/plans/` — design documents and implementation plans
- `docs/session-notes/` — development session history
- `docs/history/` — archived documentation
