# Project Goals

How much money has been spent on different parts of biomarker research (technology development, clinical biomarker discovery, biomarker translation,  clinical validation (however that is operationalized). Eventually some biomarkers are evaluated by regulatory agencies or by the medical decision making community for effectiveness. 


## Purpose of the repository

This code repository will contain skills to efficiently download NIH ExPORTER CSV files directly from https://reporter.nih.gov/exporter to achieve the goals of the project. 
The code should not rely on search word filters. The reliance of filters must be general and for the broadest level of whittling down the large pool of papers and mainly for the purpose of making the datasets more manageable. Finally use LLM graders to evaluate when a project meets some research specification given by the user. 


The workflow is:
- Download NIH ExPORTER data directly (https://reporter.nih.gov/exporter) and extract a targeted subset using permissive biomarker/adjacency heuristics to keep datasets small (~10-50 MB per year/cohort).

- Standardize the dataset for project goals

- Classify each project into biomarker phases of interest: technology development, biomarker discovery, biomarker validation, and occasionally biomarker qualification for regulatory approval. However, biomarker research is more complicated than that, so we will also dig into research funding given to different biomarker contexts of use such as diagnostics, clinical trial enrichment, or surrogate endpoints. 

- For complicated classification of project abstracts, use an LLM grader with a documented rubric and prompts;

- Perform user specified aggregation of the data. Potentially by research phase, NIH institute, funding mechanism, and year.  

- Export analysis tables and small artifacts for review.

- (optional) Build a dashboard that can be hosted on gradio to view existing dataset. 


## Data
We extract a smaller, targeted dataset from NIH ExPORTER focused on biomarker and biomarker‑adjacent research.

- Primary source: NIH ExPORTER (official): https://reporter.nih.gov/exporter
- Alternative: SciOP NIH Reporter snapshots: https://sciop.net/datasets/nih-reporter (mirrors may lag)


Coding agents should read .agents/AGENTS.md for further instructions

