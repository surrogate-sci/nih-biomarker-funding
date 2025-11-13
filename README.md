# Project Goals

How much money has been spent on different parts of biomarker research (technology development, clinical biomarker discovery, biomarker translation,  clinical validation (however that is operationalized). Eventually some biomarkers are evaluated by regulatory agencies or by the medical decision making community for effectiveness.


## Purpose of the repository

This code repository analyzes NIH biomarker research funding using LLM-based classification to understand spending patterns across different research phases and contexts of use. The code downloads NIH ExPORTER CSV files directly from https://reporter.nih.gov/exporter, uses broad keyword filters to create manageable datasets, then employs LLM graders to classify projects into specific research categories.

The code should not rely solely on search word filters. The reliance on filters must be general and for the broadest level of whittling down the large pool of papers and mainly for the purpose of making the datasets more manageable. Finally use LLM graders to evaluate when a project meets some research specification given by the user.


The workflow is:
- Download NIH ExPORTER data directly (https://reporter.nih.gov/exporter) and extract a targeted subset using permissive biomarker/adjacency heuristics to keep datasets small (~10-50 MB per year/cohort).

- Combine and deduplicate multiple searches to create a unified dataset

- Standardize the dataset for project goals

- Classify each project into biomarker phases of interest: technology development, biomarker discovery, biomarker validation, and occasionally biomarker qualification for regulatory approval. However, biomarker research is more complicated than that, so we will also dig into research funding given to different biomarker contexts of use such as diagnostics, clinical trial enrichment, or surrogate endpoints.

- For complicated classification of project abstracts, use an LLM grader with a documented rubric and prompts;

- Perform user specified aggregation of the data. Potentially by research phase, NIH institute, funding mechanism, and year.

- Export analysis tables and small artifacts for review.

- (optional) Build a dashboard that can be hosted on gradio to view existing dataset.


## Data

### Data Sources

- Primary source: NIH ExPORTER (official): https://reporter.nih.gov/exporter
- Alternative: SciOP NIH Reporter snapshots: https://sciop.net/datasets/nih-reporter (mirrors may lag)

### Current Dataset

**Oct 2024 Dataset**: `data/oct-2024/nih_biomarker_unified.csv`
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


Coding agents should read .agents/AGENTS.md for further instructions
