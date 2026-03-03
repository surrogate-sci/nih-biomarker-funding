# Calibration, Cleanup & Scale-Up Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Commit calibration infrastructure, clean up obsolete code, and prepare the pipeline for 270K-grant classification with a 3-model ensemble strategy.

**Architecture:** Two cheap models (Gemini 2.5 Flash Lite + GPT-4o-mini) classify all grants; disagreements (~28%) go to Sonnet 4.6 Batch API as tiebreaker. Total estimated cost ~$700-900.

**Tech Stack:** Python 3.10+, OpenRouter API, Anthropic Batch API (for Sonnet tiebreaker)

---

## Task 1: Commit Calibration Infrastructure

Commit the new `run_calibration.py` script and calibration results from all 3 models.

**Files:**
- Track: `scripts/run_calibration.py`
- Track: `data/calibration_results_gemini-2.0-flash-001.json`
- Track: `data/calibration_results_gemini-2.5-flash-lite.json`
- Track: `data/calibration_results_gpt-4o-mini.json`

**Step 1: Stage and commit**

```bash
git add scripts/run_calibration.py
git add -f data/calibration_results_gemini-2.0-flash-001.json
git add -f data/calibration_results_gemini-2.5-flash-lite.json
git add -f data/calibration_results_gpt-4o-mini.json
git commit -m "grade: add calibration runner and results for 3 models

Calibration on 25 easy cases with explicit biomarker terms.
Models: Gemini 2.0 Flash, Gemini 2.5 Flash Lite, GPT-4o-mini.
28% inter-model disagreement rate on Dimension 1 (biomarker_use)."
```

---

## Task 2: Update Design Doc

Update `docs/plans/2026-03-02-rubric-grader-pipeline-design.md` to reflect:
- Model selection decisions (Gemini 2.5 Flash Lite + GPT-4o-mini primary, Sonnet 4.6 tiebreaker)
- Cost estimates ($183 + $275 primary + ~$200-500 tiebreaker)
- Calibration results (25/25 success, 28% disagreement on Dim1)
- Closed open questions (which LLMs, ensemble strategy)

**Files:**
- Modify: `docs/plans/2026-03-02-rubric-grader-pipeline-design.md`

**Step 1: Update the design doc**

Replace the "Open Questions" section with resolved decisions. Update status from "In progress" to reflect calibration completion.

**Step 2: Update CLAUDE.md**

Add model selection decisions and calibration results to the "Current Status" section.

**Step 3: Commit**

```bash
git add docs/plans/2026-03-02-rubric-grader-pipeline-design.md CLAUDE.md
git commit -m "docs: update design doc with model selection and calibration results"
```

---

## Task 3: Code Cleanup (PR, not direct commit)

Create a cleanup PR removing obsolete code and tightening the active codebase. **Do NOT commit directly to main.**

**Files to remove or archive:**
- `scripts/dedupe_and_union.py` — Oct-2024-only script, not in current pipeline
- `scripts/nih_bulk_downloader.py` — Outdated, replaced by `process_all_years.py`
- `data/oct-2024/` — Legacy analysis with different keyword strategy (6 tracked files)

**Files to clean up:**
- `scripts/grader_prompt.py` — Remove `_LEGACY_SYSTEM_PROMPT` (569→~300 lines), remove `run_comparison()` and `call_openai()` (dead code superseded by `run_calibration.py`), remove `test_grader()` (inline test cases, not a real test suite). Keep: `load_rubric()`, `build_system_prompt()`, `create_grading_prompt()`, `call_openrouter()`, `OUTPUT_SCHEMA`.
- `README.md` — Update to reflect current pipeline (currently describes old workflow)

**Files to strip from grader prompt (token optimization):**
- Update `build_system_prompt()` to strip the `> SOURCE OF TRUTH` preamble and `## References` section from RUBRIC.md before injecting into the prompt. Saves ~100 tokens per call.

**Step 1: Create branch**

```bash
git checkout -b cleanup/remove-obsolete-code
```

**Step 2: Remove obsolete scripts**

```bash
git rm scripts/dedupe_and_union.py
git rm scripts/nih_bulk_downloader.py
```

**Step 3: Remove tracked oct-2024 data**

```bash
git rm data/oct-2024/nih_biomarker_unified.csv
git rm data/oct-2024/all_biomarkers_filtered.csv
git rm data/oct-2024/biomarker_discovery_filtered.csv
git rm data/oct-2024/biomarker_validation_filtered.csv
git rm data/oct-2024/surrogate_endpoints_filtered.csv
git rm data/oct-2024/results_summary.md
```

**Step 4: Slim down grader_prompt.py**

Remove `_LEGACY_SYSTEM_PROMPT`, `test_grader()`, `run_comparison()`, `call_openai()`, and the `if __name__ == "__main__"` block. The script becomes a library module only, invoked by `run_calibration.py`.

Add rubric stripping to `build_system_prompt()`:

```python
def _strip_rubric_for_prompt(rubric_text: str) -> str:
    """Remove documentation-only sections from rubric before prompt injection."""
    lines = rubric_text.split("\n")
    filtered = []
    skip = False
    for line in lines:
        # Skip the "SOURCE OF TRUTH" preamble
        if line.startswith("> **SOURCE OF TRUTH**"):
            continue
        # Skip References section
        if line.startswith("## References"):
            skip = True
            continue
        if skip and line.startswith("## "):
            skip = False
        if not skip:
            filtered.append(line)
    return "\n".join(filtered)
```

**Step 5: Update README.md**

Rewrite to describe current 3-step pipeline: Filter → Classify (LLM) → Aggregate.

**Step 6: Commit and create PR**

```bash
git add -A
git commit -m "cleanup: remove obsolete scripts, slim grader_prompt.py, update README

- Remove dedupe_and_union.py (Oct-2024 only)
- Remove nih_bulk_downloader.py (replaced by process_all_years.py)
- Remove tracked oct-2024/ data files
- Remove legacy prompt, dead code from grader_prompt.py
- Strip non-grading sections from RUBRIC.md in prompt
- Update README for current pipeline"

gh pr create --title "Remove obsolete code and slim grader_prompt.py" --body "## Summary
- Remove 2 obsolete scripts and Oct-2024 legacy data
- Slim grader_prompt.py from 569 to ~150 lines (remove legacy prompt, dead code)
- Strip documentation-only sections from RUBRIC.md before prompt injection (~100 token savings)
- Update README to reflect current pipeline

## Test plan
- [ ] Verify run_calibration.py still works after grader_prompt.py cleanup
- [ ] Verify no import errors from removed files
- [ ] Review README accuracy"
```

---

## Task 4: Build Batch Classification Script

Build the script that runs the full 270K-grant classification pipeline.

**Files:**
- Create: `scripts/run_classification.py`
- Create: `scripts/join_abstracts.py`

**Step 1: Write abstract joiner**

Script to join abstracts from `~/Downloads/RePORTER_PRJABS_C_FY*.zip` to the main dataset. Handle missing FY2016 gracefully.

**Step 2: Write batch classifier**

Script that:
- Reads joined dataset (title + abstract)
- Calls Model 1 (Gemini 2.5 Flash Lite) on all grants
- Calls Model 2 (GPT-4o-mini) on all grants
- Identifies disagreements
- Calls Model 3 (Sonnet 4.6 via Anthropic Batch API) on disagreements only
- Saves results with checkpointing (resume from last successful grant)
- Rate limiting and error handling

**Step 3: Test on 100 grants**

Run on first 100 grants to validate pipeline end-to-end.

**Step 4: Commit**

```bash
git add scripts/run_classification.py scripts/join_abstracts.py
git commit -m "grade: add batch classification pipeline with 3-model ensemble"
```

---

## Task 5: Sample Hard Cases

Sample grants without explicit biomarker terms for robustness testing.

**Files:**
- Create: `data/grader_hard_cases.csv`

**Step 1: Sample ~50 grants**

From the unified dataset, select grants that:
- Were matched by broad "biomarker" keyword only
- Do NOT contain explicit terms (surrogate, pharmacodynamic, prognostic, predictive, etc.)
- Span multiple years and institutes

**Step 2: Run all 3 models on hard cases**

**Step 3: Present disagreements to Manjari for adjudication**

---

## Execution Order

1. **Task 1** (commit calibration) — immediate, no dependencies
2. **Task 2** (update docs) — immediate, no dependencies
3. **Task 3** (cleanup PR) — independent, parallel with 1-2
4. **Task 4** (batch classifier) — after Task 3 is merged (depends on slimmed grader_prompt.py)
5. **Task 5** (hard cases) — after Task 4 (uses batch classifier)
