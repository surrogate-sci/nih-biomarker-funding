# Session Notes: 2026-03-19 — Dataset Release & Access

## Goal

Produce an internal data analysis with figures explaining what we have so far — not for
public posting, but to characterize the crude ~270K grant dataset before LLM grading refines it.

### Analysis goals

1. **Define the biomarker research universe** — explain core terms (4) vs. expanded terms (10),
   what "biomarker-adjacent" means, and acknowledge data quality gaps (e.g., missing grants in
   some years due to empty PROJECT_TERMS fields)

2. **Funding summaries**:
   - Total funding across all NIH
   - Broken down by institute
   - Broken down by year (trends over time)

3. **Biomarker type distribution** — how often are diagnostic/risk biomarkers studied vs.
   intermediate outcome, clinical endpoint, or surrogate endpoint biomarkers?

4. **Grant mechanism breakdown** — R01 (basic/early-stage research) vs. clinical trial grant
   types, showing that surrogacy validation is underrepresented in earlier research stages

### Background

- The 270K grant dataset is a crude keyword-filtered approximation with known gaps
- Edison (prior agent) couldn't distinguish surrogate/causal evidence from non-causal —
  that's why we're building the rubric-based LLM grading system
- This analysis characterizes the *pre-grading* dataset to understand what we're working with

## What was tried

Multiple approaches to get the file into the session environment all failed:
- **Claude chat upload**: 130MB exceeds the ~10MB upload limit
- **Figshare**: dataset may be hosted there but URL not confirmed; API search didn't find it
- **GitHub release download**: proxy/firewall in the sandbox blocks GitHub file downloads (403 on CONNECT)
- **Unrestricted internet setting**: user enabled it but it didn't take effect mid-session

## What was done

1. **Dataset published as GitHub release** — the unified dataset (130MB CSV, 269,630 grants)
   was uploaded by Manjari via the GitHub web UI:
   - **Download URL**: https://github.com/surrogate-sci/nih-biomarker-funding/releases/download/dataset-release-v1.0/nih_biomarker_unified_2004-2024.zip
   - Release tag: `dataset-release-v1.0`

2. **Download instructions** — to get the dataset into the working directory:
   ```bash
   curl -L -o data/nih_biomarker_unified_2004-2024.zip \
     "https://github.com/surrogate-sci/nih-biomarker-funding/releases/download/dataset-release-v1.0/nih_biomarker_unified_2004-2024.zip"
   unzip data/nih_biomarker_unified_2004-2024.zip -d data/
   ```

3. **Environment note** — the sandbox proxy blocks GitHub file downloads (403 on CONNECT tunnel).
   If `curl`/`wget` fail, the user may need to grant unrestricted network access before session start,
   or download the file locally first.

## Next session

- **Primary goal**: Download the dataset and produce the analysis described above (figures + narrative)
- Ensure unrestricted internet is enabled *before* session starts so `curl`/`wget` can reach GitHub
- Figshare mirror may also exist (Manjari mentioned it) but URL not confirmed
- This is internal/exploratory work — nothing goes to public repo yet
