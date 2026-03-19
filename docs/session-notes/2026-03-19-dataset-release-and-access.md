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

### Session 2 attempts (same day)

- **Tag confirmed**: `git ls-remote --tags origin` shows `dataset-release-v1.0` exists
- **Release asset 404**: The download URL returns "Not Found" — the release may not have an
  asset attached, or the release was created as a tag without uploading the zip via the Releases UI
- **`gh` CLI**: Not pre-installed; installed via apt but no GitHub token available for auth
- **Proxy limitation**: The sandbox git proxy (`127.0.0.1:42449`) only handles git protocol,
  not GitHub API or release asset downloads
- **No `GITHUB_TOKEN`**: Environment has no GitHub token set, so authenticated API calls fail

## What was done

1. **Dataset published as GitHub release** — the unified dataset (130MB CSV, 269,630 grants)
   was uploaded by Manjari via the GitHub web UI:
   - **Download URL**: https://github.com/surrogate-sci/nih-biomarker-funding/releases/download/dataset-release-v1.0/nih_biomarker_unified_2004-2024.zip
   - Release tag: `dataset-release-v1.0`
   - **Status**: Tag exists but asset download returns 404 — needs verification

2. **Download instructions** — preferred method using `gh` (requires auth):
   ```bash
   # Option A: gh CLI (if GITHUB_TOKEN is set or gh is logged in)
   gh release download dataset-release-v1.0 --repo surrogate-sci/nih-biomarker-funding --dir data/
   unzip data/nih_biomarker_unified_2004-2024.zip -d data/

   # Option B: curl with token
   curl -L -H "Authorization: token $GITHUB_TOKEN" \
     -o data/nih_biomarker_unified_2004-2024.zip \
     "https://github.com/surrogate-sci/nih-biomarker-funding/releases/download/dataset-release-v1.0/nih_biomarker_unified_2004-2024.zip"
   unzip data/nih_biomarker_unified_2004-2024.zip -d data/

   # Option C: curl (only works if repo is public or unrestricted internet is enabled)
   curl -L -o data/nih_biomarker_unified_2004-2024.zip \
     "https://github.com/surrogate-sci/nih-biomarker-funding/releases/download/dataset-release-v1.0/nih_biomarker_unified_2004-2024.zip"
   unzip data/nih_biomarker_unified_2004-2024.zip -d data/
   ```

3. **Environment requirements for dataset download in Claude Code web sessions**:
   - Set `GITHUB_TOKEN` env var before session start, OR
   - Enable unrestricted internet before session start (not mid-session), OR
   - Upload the file directly to the session (only if <10MB or split)

## Next session

- **Verify release**: Check https://github.com/surrogate-sci/nih-biomarker-funding/releases
  to confirm the zip was actually uploaded as a release asset (not just a tag)
- **Primary goal**: Download the dataset and produce the analysis (figures + narrative)
- **Auth fix**: Set `GITHUB_TOKEN` in Claude Code env vars before starting session
- Figshare mirror may also exist (Manjari mentioned it) but URL not confirmed
- This is internal/exploratory work — nothing goes to public repo yet
