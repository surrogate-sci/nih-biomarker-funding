# Session Notes: 2026-03-19 — Dataset Release & Access

## What was done

1. **Dataset published as GitHub release** — the unified dataset (130MB CSV, 269,630 grants)
   is too large for git or Claude chat upload. Manjari uploaded it via the GitHub web UI:
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

## Open items

- Dataset needs to be downloaded and unzipped into `data/` before any analysis scripts can run
- Figshare mirror may also exist (Manjari mentioned it) but URL not confirmed
