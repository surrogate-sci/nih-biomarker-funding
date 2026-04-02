# Merge Worktrees & Code Quality Plan

**Status:** Phase 1 complete (worktree merge); Inspect AI migration done via PR #18

**Goal:** Consolidate diverged worktree branches into main, fix code quality issues
identified by holistic code review, and prepare the codebase for Inspect AI migration
and the 270K-grant production run.

**Scope:** Merge-first + code quality. Does NOT include the full Inspect AI migration
or W&B integration (those remain Issues #7 and #8).

**Triggered by:** Code review on 2026-03-09 identifying 4 critical, 6 important, and
7 suggestion-level issues across the project.

---

## Phase 1: Pre-Merge Audit & Branch Consolidation

### Step 0: Audit worktree artifacts

Before any merge, diff both worktrees against main to ensure no untracked or
uncommitted artifacts will be lost. This is a research project — intermediate
products (grades, agreement analyses, expert reviews) are not disposable.

```bash
# For each worktree: check for uncommitted/untracked files
cd .claude/worktrees/ecstatic-bassi && git status && git stash list
cd .claude/worktrees/jolly-ishizaka && git status && git stash list

# Diff each branch against main
git diff --stat main...claude/ecstatic-bassi
git diff --stat main...claude/jolly-ishizaka
```

Commit any untracked artifacts before proceeding. Flag anything ambiguous
to Manjari for confirmation.

### Step 1: Merge PR #10 (jolly-ishizaka cleanup)

PR #10 removes `dedupe_and_union.py`, slims `grader_prompt.py` (568→~190 lines),
adds `_strip_rubric_for_prompt()`, updates README. Already reviewed.

- Fix `analyze_keywords.py` column name mismatch (I2) before merge
- Merge to main

### Step 2: Rebase ecstatic-bassi onto new main

ecstatic-bassi has 21 files changed (+3,379/-791 lines) including:

**Scripts:**
- `scripts/utils.py` — shared utilities (`load_env()`, `parse_llm_json()`)
- `scripts/abstract_loader.py` — RePORTER abstract ZIP loading
- `scripts/run_batch_grading.py` — batch LLM grading with checkpoint/resume
- `scripts/sample_oncology.py` — stratified NCI grant sampling
- `scripts/analyze_agreement.py` — inter-model agreement analysis
- `scripts/extract_disagreements.py` — disagreement pattern extraction
- `scripts/generate_review.py` — anti-anchoring expert review HTML
- `tests/test_generate_review.py` — unit tests

**Data artifacts (~10MB total):**
- `data/oncology_grades_gemini-2.5-flash-lite.jsonl` (2,309 grades, 3.2MB)
- `data/oncology_grades_gpt-4o-mini.jsonl` (233 grades, 260KB)
- `data/oncology_grades_gpt-4.1-mini.jsonl` (159 grades, 196KB)
- `data/oncology_sample_100per_year.csv` (5.2MB)
- `data/disagreement_examples.json` + `.csv`
- `data/expert_grades_calibration_v1.json`
- `data/expert_review.html` + `data/expert_review_disagreements.html`
- `data/oncology_agreement_analysis.txt`

**Docs:**
- `docs/plans/2026-03-04-codebase-cleanup-and-api-architecture.md`
- `docs/session-notes/2026-03-04-scale-experiment-api-review.md`
- `docs/analysis/2026-03-04-rubric-grading-status.md`

**Conflict resolution strategy for `grader_prompt.py`:**
- Keep jolly-ishizaka's slim version (PR #10) as the base
- Add back `call_openai()` from ecstatic-bassi (needed by `run_batch_grading.py`)
- Keep `_strip_rubric_for_prompt()` from jolly-ishizaka

### Step 3: PR ecstatic-bassi → main

Full merge including all data artifacts, scripts, docs, and tests.

### Step 4: Clean up stale branches

After merge, delete worktree branches and directories.

---

## Phase 2: Code Quality Fixes

Apply on a new branch from the merged main.

### C1: Add `pyproject.toml`

```toml
[project]
name = "nih-biomarker-funding"
requires-python = ">=3.10"
dependencies = [
    "pandas>=2.0",
    "requests>=2.28",
    "matplotlib>=3.7",
    "numpy>=1.24",
    "jsonschema>=4.0",
]

[project.optional-dependencies]
dev = ["ruff", "pytest"]
```

### C2: Fix CI

Replace `.github/workflows/pylint.yml` with a workflow that:
- Tests Python 3.10+ only (codebase uses `int | None` syntax)
- Installs project dependencies from `pyproject.toml`
- Runs `ruff check` (not `pylint`)
- Runs `pytest` if tests exist

### C3: Add JSON schema validation to `grader_prompt.py`

Add `validate_classification(result: dict) -> list[str]` that checks:
- `biomarker_use.primary` against Dim1 enum values
- `research_design.primary` against Dim2 enum values
- `evidence_strength.primary` against Dim3 enum values
- Required fields present

Called by `run_batch_grading.py` — invalid classifications logged as errors
with the raw response preserved for debugging, not silently accepted.

### I1: Remove hardcoded data from `plot_funding_overview.py`

Read funding data from `data/filtered/SUMMARY.md` or directly from year CSVs
instead of Python list literals that go stale.

### I2: Fix column names in `analyze_keywords.py`

Replace legacy column names with unified dataset schema:
- `'Project Title'` → `'PROJECT_TITLE'`
- `'Total Cost'` → `'TOTAL_COST'`
- `'Fiscal Year'` → `'FY'`
- `'Administering IC'` → `'ADMINISTERING_IC'`
- `'Application ID'` → `'APPLICATION_ID'`

### I3: Fix `create_html_charts.py` data sources

Update to read from correct upstream files or make self-contained by reading
from the unified dataset directly.

### I4: Fix `extract_examples.py` hardcoded path

Add `argparse` for abstract file path, matching the CLI convention of other scripts.

### I6: Consolidate `.env` loading

ecstatic-bassi's `utils.py` already has `load_env()`. After merge, update
`run_calibration.py` to import from `utils.py` instead of inlining.

### S7: Fix `EXPLICIT_BIOMARKER` boolean comparison

In `generate_summary.py`, normalize on CSV read:
```python
df['EXPLICIT_BIOMARKER'] = df['EXPLICIT_BIOMARKER'].astype(str).str.upper() == 'TRUE'
```

### Documentation: Clarify `EXPLICIT_BIOMARKER` semantics

Current docs describe the column mechanically ("flags core-term matches") without
explaining the analytical significance. Update CLAUDE.md and README.md:

**Current:** "`EXPLICIT_BIOMARKER` column flags core-term matches (75,849 grants, $35.77B)"

**Updated:** "All 269,630 grants in the dataset are biomarker-focused (filtered by
keyword matching). `EXPLICIT_BIOMARKER` distinguishes terminological specificity:
TRUE = matched on well-established, unambiguous terms (biomarker, clinical marker,
surrogate endpoint, imaging marker); FALSE = matched on broader or less standardized
terms (digital biomarker, endophenotype, genetic marker, etc.) that still indicate
biomarker research but with vaguer language. 75,849 grants ($35.77B) have
EXPLICIT_BIOMARKER = TRUE."

---

## Phase 3: Inspect AI Migration Prep (Stopgaps)

These are interim fixes that prevent data loss during batch runs while not
fighting the future Inspect AI architecture.

### I5: Add minimal retry to `call_openrouter()`

- Exponential backoff on 429/5xx responses (3 retries, 2/4/8s delays)
- Timeout on `urlopen()` (30s)
- This will be replaced by Inspect's model API, so keep it simple

### S6: Add metadata headers to result files

Record in each output file:
- Model name and temperature
- RUBRIC.md content hash (so you know which rubric version was used)
- Timestamp and git SHA of the run

This metadata pattern will carry forward into Inspect eval logs.

### S1: Log token usage for cost tracking

Capture `response["usage"]` from OpenRouter responses. Accumulate and print
running cost estimates. Will be replaced by W&B dashboards (Issue #8) but
prevents budget surprises during interim runs.

---

## Issue Cross-Reference

| Review Issue | Plan Section | Notes |
|---|---|---|
| C1: No dependency management | Phase 2: pyproject.toml | |
| C2: CI broken | Phase 2: Fix CI | |
| C3: No schema validation | Phase 2: validate_classification() | |
| C4: ecstatic-bassi divergence | Phase 1: Full merge | Single highest-impact action |
| I1: Hardcoded plot data | Phase 2 | |
| I2: Wrong column names | Phase 2 (fix before PR #10 merge) | |
| I3: Broken chart pipeline | Phase 2 | |
| I4: Hardcoded path | Phase 2 | |
| I5: No retry/timeout | Phase 3: Stopgap | Inspect AI replaces long-term |
| I6: Duplicated .env loading | Phase 2: Use utils.py | |
| S1: No cost tracking | Phase 3: Stopgap | W&B replaces long-term |
| S2: Flat scripts/ dir | Deferred | Not worth churn before Inspect migration |
| S3: subprocess in process_all_years | Deferred | Phase 1 scripts are stable |
| S4: Duplicated setup_logging | Deferred | Low impact |
| S5: Double CSV reads | Deferred | Low impact |
| S6: No metadata in results | Phase 3 | |
| S7: Boolean comparison bug | Phase 2 | |
| EXPLICIT_BIOMARKER docs | Phase 2 | Semantic clarification |

**Deferred items** (S2, S3, S4, S5): Not worth the churn before the Inspect AI
migration reshapes the script architecture. Revisit after Issue #7 is resolved.

---

## Appendix: Data Source Provenance (for Issue #11)

The current pipeline's PROJECT_TERMS missingness problem (FY2005 68% populated,
FY2006 empty, FY2013/FY2018 anomalous) may cause systematic undercounting of
biomarker grants in affected years.

**Two alternative data sources exist that searched abstracts:**

1. **`data/oct-2024/`** — 24,837 grants exported via NIH Reporter **web interface**
   (Oct 2024). Column format confirms web origin: mixed-case names (`Project Title`,
   `Total Cost`, `NIH Spending Categorization`), vs ExPORTER bulk format
   (`PROJECT_TITLE`, `TOTAL_COST`). The web interface searches titles, abstracts,
   and terms simultaneously — no PROJECT_TERMS missingness issue. Different keyword
   strategy (narrower: "biomarker validation", "surrogate marker", etc.).

2. **`~/Downloads/biomarker_cumulative_funding_by_year.csv`** and
   **`~/Downloads/extended_biomarker_cumulative_funding_by_year.csv`** — cumulative
   funding 1985-2025, likely from the same web-search approach. Much larger funding
   totals ($5.5B and $7.5B in FY2024) vs the ExPORTER pipeline. Provenance not
   documented — no generating script found in the repo.

**Caveat:** The oct-2024 web export used broader keywords than the current pipeline
(e.g., just "imaging" and "genomics" rather than "imaging marker"). So comparing
grant counts is not apples-to-apples: the web data overcounts (broader keywords)
while the ExPORTER data undercounts (missing PROJECT_TERMS). Still useful as a
rough upper-bound validation, but not a clean measure of the missingness effect.

**Implication for Issue #11:** The cleanest fix is to re-run Phase 1 filtering
with abstract text included for affected years, using the same keyword set as the
current pipeline. The oct-2024 data provides a rough sanity check but not a
precise benchmark due to the keyword mismatch.
