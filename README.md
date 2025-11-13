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

