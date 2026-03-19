# Session Notes: 2026-03-19 — Dataset Release & Access

## Goal

Get the unified dataset (130MB, 269,630 grants) accessible inside a Claude Code session
so the Phase 2/3 pipeline can run: LLM grading, agreement analysis, expert review, etc.
The dataset is a prerequisite for all downstream work.

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

- **Primary goal**: Download the dataset into `data/` and start running the analysis pipeline
- Ensure unrestricted internet is enabled *before* session starts so `curl`/`wget` can reach GitHub
- Figshare mirror may also exist (Manjari mentioned it) but URL not confirmed
- Once dataset is available: run grading, agreement analysis, expert review scripts
