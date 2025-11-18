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

### Automated NIH ExPORTER Analysis

**1. Filter NIH ExPORTER Data** (`scripts/filter_biomarker_projects.py`)

Filter individual fiscal year data for biomarker-related projects:

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

**Output:** Adds `EXPLICIT_BIOMARKER` column (TRUE/FALSE) to flag projects matching core terms.

**2. Batch Process Multiple Years** (`scripts/process_all_years.py`)

Process multiple fiscal years from NIH ExPORTER data:

```bash
# Process years 2020-2024 with existing downloads
python3 scripts/process_all_years.py \
  --start-year 2020 \
  --end-year 2024 \
  --skip-download \
  --raw-dir ~/Downloads \
  --term-set expanded

# Download and process years 2020-2024 automatically
python3 scripts/process_all_years.py \
  --start-year 2020 \
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
- Data quality notes (e.g., FY2005-2006 PROJECT_TERMS issues)

### Workflow

1. **Heavy processing** (once): `process_all_years.py` - filters raw NIH ExPORTER data
2. **Light reporting** (anytime): `generate_summary.py` - creates reports from filtered CSVs


## Data

**Current Dataset**: `data/nih_biomarker_unified.csv`
- 24,837 unique projects (Application ID + Fiscal Year combinations)
- Spans FY1988 - FY2024
- 60.6 MB CSV file
- Sourced from NIH Reporter searches using biomarker-related keywords:
  - "biomarker validation"
  - "surrogate marker", "intermediate endpoint", "endophenotype", "surrogate biomarker"
  - Includes full project abstracts, public health relevance statements, and funding metadata

**Top Institutes**: NCI (6,999), NIA (2,809), NIMH (2,638), NINDS (1,930), NHLBI (1,666)


### Results from Analyzing Oct 2024 export

#### Biomarker Discovery
This is a an underestimate as we just included "biomarker discovery" as a search term. 

  "Biomarker Discovery" Projects: 1,654 (6.4% of total dataset)
  - Total Funding: $817.69M (2009-2024)
  - Average per Project: $503,501
  - Peak Year: FY2023 with $115.78M (232 projects)

  Funding Growth Pattern:
  - Major ramp-up started in FY2016 (~135 projects, $84M)
  - Steady growth through FY2023
  - FY2024 shows $49M (partial year data)

  Top Funding Institutes:
  1. NCI - $260M (596 projects) - Cancer research dominates
  2. NIA - $179M (193 projects) - Aging research
  3. NINDS - $90M (143 projects) - Neurological diseases
  4. NIDDK - $72M (142 projects) - Diabetes/kidney/digestive


#### Intermediate outcomes and Surrogate endpoints


  Surrogate/Intermediate Endpoint Projects: 226 (0.9% of total dataset)
  - Total Funding: $260.00M (1989-2024)
  - Average per Project: $1,232,224 (significantly higher than biomarker discovery!)
  - Peak Year: FY2024 with $61.55M (27 projects)

  Keyword Breakdown:
  - "surrogate endpoint": 197 projects
  - "intermediate endpoint": 29 projects
  - "intermediate outcomes": 0 projects

  Funding Growth Pattern:
  - Early work in late 1980s-2000s
  - Slow growth 2007-2020 (~$0.4-10M/year)
  - Major acceleration starting FY2021: $36M → $55M → $49M → $62M
  - Recent years (2021-2024) account for most funding

  Top Funding Institutes:
  1. NIAID - $116M (9 projects) - Very high per-project average!
  2. NCI - $58M (92 projects) - Most projects but lower per-project
  3. NIA - $48M (13 projects) - Aging research
  4. NHLBI - $10M (21 projects) - Heart/lung/blood

 Observations:
  - Much smaller than biomarker discovery (226 vs 1,654 projects)
  - But higher average cost per project ($1.2M vs $500K)
  - NIAID dominates funding despite having fewest projects - suggests large clinical trials
  - Very recent acceleration (2021-2024)