# Calibration, Cleanup & Scale-Up Plan

**Status:** Partially complete — calibration done, scale-up superseded by Inspect AI migration

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Commit calibration infrastructure, clean up obsolete code, and prepare the pipeline for 270K-grant classification with a 3-model ensemble strategy.

**Architecture:** Two cheap models (Gemini 2.5 Flash Lite + GPT-4.1-mini) classify all grants; disagreements (~28%) go to Sonnet 4.6 Batch API as tiebreaker. Total estimated cost ~$350-480 with Inspect batch mode.

**Tech Stack:** Python 3.10+, Inspect AI (UK AISI eval framework — handles batch API, retry, caching, logging), direct provider APIs for production (OpenAI, Google, Anthropic), OpenRouter for calibration comparisons.

> **Note (2026-03-29):** Task 4 (batch classifier) is superseded by the Inspect AI migration (Issue #7). The hand-rolled `run_batch_grading.py` is replaced by `inspect eval` / `inspect eval-set --batch`.

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

## Task 4: ~~Build Batch Classification Script~~ → Inspect AI Migration (Issue #7)

> **Superseded (2026-03-29):** Hand-rolled batch classifier replaced by Inspect AI migration.
> See Issue #7 for the full migration plan.

**What Inspect provides instead of a custom script:**
- `inspect eval --batch` for provider batch APIs (50% cost savings)
- `inspect eval-set` for multi-model runs with automatic retry/resume
- Caching (`--cache`) to avoid re-running identical prompts
- `.eval` logs with `inspect view` for structured experiment tracking
- `inspect-wandb` for W&B integration (Issue #8)

**Phased rollout:**
1. Calibration (25 examples): `inspect eval` with OpenRouter
2. Mid-scale (~10-20K grants per institute/year): `inspect eval` with direct provider APIs
3. Full 270K production: `inspect eval-set --batch` with OpenAI/Google batch APIs

**Still needed:** `scripts/abstract_loader.py` for joining abstracts to the Inspect Dataset via `record_to_sample`.

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

## Task 6: Calibration Comparison Script

Build a reusable script that compares calibration results across models, replacing ad-hoc analysis.

**Why a script, not a skill:** This is a repeatable data task with specific inputs/outputs (JSON files in, comparison table out). Skills tell Claude *how to work*; this is *work to be done*.

**Files:**
- Create: `scripts/compare_calibration.py`

**Behavior:**
- Load all `data/calibration_results_*.json` files
- Compute per-example agreement matrix across models (all dimensions)
- Identify disagreement cases with specific dimension/code pairs
- Output: summary table (stdout) + detailed disagreements CSV
- Optionally filter by dimension or confidence level

```bash
# Compare all models
python3 scripts/compare_calibration.py

# Compare specific models on Dim1 only
python3 scripts/compare_calibration.py --dim biomarker_use --models gemini-2.5-flash-lite gpt-4o-mini
```

**Step 1: Write the script**

**Step 2: Run on existing calibration results to verify**

**Step 3: Commit**

```bash
git add scripts/compare_calibration.py
git commit -m "grade: add calibration comparison script"
```

---

## Execution Order & Status

| Task | Status | Dependencies | Notes |
|------|--------|-------------|-------|
| Task 1: Commit calibration | ✅ Done (`1067cc8`) | — | |
| Task 2: Update docs | ✅ Done (`85a1a42`, `a10a7ec`, `b7d2f20`) | — | |
| Task 3: Cleanup PR | **Next** | — | Must be a PR, not direct commit |
| Task 4: Batch classifier | Pending | Task 3 merged | Depends on slimmed grader_prompt.py |
| Task 5: Hard cases | Pending | Task 4 | Uses batch classifier |
| Task 6: Calibration comparison | Pending | — | Independent, can do anytime |
