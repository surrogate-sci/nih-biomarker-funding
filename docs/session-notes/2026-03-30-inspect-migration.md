# Session Notes: 2026-03-30 — Inspect AI Migration

## Goal

Design and implement a lightweight Inspect AI task (`inspect_task.py`) that replaces
the hand-rolled grading scripts (`run_calibration.py`, `run_batch_grading.py`) with a
single entry point that works at all scales — from 25-example calibration runs to the
full 270K production run via batch API.

## What was tried

- **Initial approach (eval-only)**: Recommended keeping hand-rolled scripts for
  production and only using Inspect for evaluation. Manjari corrected: Inspect's
  native batch API support (`--batch` flag for OpenAI/Anthropic/Google) makes it
  strictly better than anything hand-rolled. Revised to full migration.

- **Over-engineering**: Early drafts focused too much on batch infrastructure.
  Manjari clarified the priority ordering: great eval logging and model/judge
  swapping first, batch compatibility as a gate for the 270K run when rubric and
  data quality are ready.

## What was done

1. **Design doc** — `docs/plans/2026-03-30-inspect-task-design.md` (8 tasks, TDD steps)

2. **Implementation** (`inspect_task.py`):
   - `parse_rubric_codes()` — parses valid codes from RUBRIC.md via regex at import time (not hardcoded)
   - `record_to_sample()` — handles oncology, calibration, and gold-labeled CSV formats
   - `rubric_solver()` — injects RUBRIC.md system prompt via `scripts.grader_prompt`
   - `rubric_scorer()` — multi-valued Score with `valid_json` and `valid_codes` metrics, full classification metadata
   - `_parse_classification()` / `_validate_codes()` — JSON extraction with per-dimension code validation
   - `biomarker_grading()` @task — composes Dataset + Solver + generate() + Scorer
   - `GenerateConfig()` empty — temperature/max_tokens controlled via CLI
   - Gold-label support: `GOLD_DIM1/DIM2/DIM3` CSV columns → `Sample.target`

3. **Tests** (`tests/test_inspect_task.py`, 31 tests, all passing):
   - Dataset loader: oncology format, calibration format, missing abstract, template match, gold labels, partial gold labels
   - Code enums: count assertions per dimension, rubric parsing round-trip, specific codes present
   - Solver: callable, system prompt content, references excluded
   - Parser: valid JSON, markdown-fenced, bare-fenced, malformed, non-dict, invalid code reporting
   - Task: returns Task instance, has solver/scorer, no hardcoded config defaults

4. **Smoke test** — 3 grants graded via `inspect eval inspect_task.py --model openrouter/google/gemini-2.5-flash-lite --limit 3`:
   - 100% valid_json, 100% valid_codes
   - Structured `.eval` logs readable programmatically
   - End-to-end pipeline confirmed working

5. **Documentation updates**:
   - `CLAUDE.md` — Phase 2 shows current vs target architecture, Inspect commands added
   - `docs/plans/2026-03-02-rubric-grader-pipeline-design.md` — Inspect migration path
   - `docs/plans/2026-03-02-calibration-cleanup-scale.md` — Task 4 marked superseded
   - `docs/plans/2026-03-04-codebase-cleanup-and-api-architecture.md` — API fixes moot note
   - GitHub Issue #7 — Rewritten with Inspect capabilities, phased rollout
   - GitHub Issue #8 — Updated for Inspect logging + inspect-wandb path

6. **PR #18** — https://github.com/surrogate-sci/nih-biomarker-funding/pull/18

7. **Issue #20** — Grader sensitivity analysis plan (temperature, inter-model, disagreement patterns, gold-label calibration). Covers execution order, Inspect mechanisms, and cost estimates for 3K oncology sample.

8. **Environment setup**:
   - `uv venv .venv --python 3.14` + `uv pip install inspect-ai openai ruff`
   - `.env` copied from main repo for API keys
   - `logs/` added to `.gitignore`

9. **Judge evaluation ecosystem research**:
   - **HiBayES** (AISI) — Hierarchical Bayesian analysis, reads `.eval` natively
   - **CJE** — Calibrates cheap judge against oracle slice with valid CIs
   - **RAND JRH** — Perturbation stress tests (format invariance, verbosity bias, label flip, paraphrase)

## Bugs fixed during review

- Scorer returned single CORRECT/INCORRECT instead of multi-valued dict
- `_parse_classification` didn't report which dimension codes are invalid
- `has_abstract` and `explicit_biomarker` stored as strings, not Python bools
- Non-dict JSON (e.g., `[1,2,3]`) crashed `_parse_classification`

## Next session

- **Manjari reviews PR #18** — merge or request changes
- **Test with direct providers** — `google/gemini-2.5-flash-lite` and `openai/gpt-4.1-mini`
  (needs those API keys configured in `.env`)
- **Batch mode test** — `inspect eval inspect_task.py --batch --limit 10` with a direct provider
- **`inspect view`** — manually verify the web UI shows structured results correctly
- **Multi-model comparison** — `inspect eval-set` with two models
- **Sensitivity runs** — start with temperature self-consistency (Issue #20, step 1)
- **Data quality** — fix missing abstracts / FY2016 gap before scaling to 270K
