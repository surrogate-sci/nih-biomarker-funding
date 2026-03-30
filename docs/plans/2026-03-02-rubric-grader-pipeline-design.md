# Design: Rubric-Driven Grader Pipeline

**Date:** 2026-03-02 (updated 2026-03-29)
**Status:** Calibration complete; migrating to Inspect AI for scale-up (Issue #7)

## Problem

The LLM grader for classifying ~270K NIH biomarker grants needs:
1. A precise classification rubric (RUBRIC.md) — **done, pending review**
2. A grader that loads the rubric at runtime instead of hardcoding it
3. Calibration testing on known examples
4. Hard-case sampling for robustness testing
5. Full dataset classification

Previous Kosmos analysis had ~50% ambiguous classifications due to a binary causal/correlational schema and zero-shot prompting without a rigorous rubric.

## Architecture

### Current (hand-rolled scripts — being replaced)

```
data/RUBRIC.md          ← source of truth (17 + 10 + 5 codes)
        ↓
scripts/grader_prompt.py ← reads RUBRIC.md, constructs prompt, calls LLM API
        ↓
data/grader_calibration_examples.csv  ← 25 easy cases (explicit biomarker terms)
data/grader_hard_cases.csv            ← TBD, grants without explicit terms
        ↓
data/grader_results/                  ← per-model classification outputs (JSONL)
```

### Target (Inspect AI — Issue #7)

```
data/RUBRIC.md          ← source of truth (unchanged)
        ↓
inspect_task.py         ← Inspect Task: Dataset + Solver + Scorer
  ├─ Solver             ← reuses grader_prompt.py (build_system_prompt, message formatting)
  ├─ Scorer             ← parses JSON, validates codes, multi-valued Score (dim1, dim2, dim3)
  └─ Dataset            ← csv_dataset with record_to_sample (APPLICATION_ID → id, title+abstract → input)
        ↓
inspect eval / eval-set ← runs grading with batch API, retry, caching, multi-model
        ↓
logs/*.eval             ← structured logs (inspect view for browsing, inspect-wandb for W&B)
```

**Why Inspect replaces the full pipeline (not just eval):**
- Batch API support for OpenAI, Anthropic, Google — 50% cost savings on production runs
- `eval-set` handles multi-model comparison with automatic retry, sample preservation, resume
- Caching avoids re-running identical prompts during rubric iteration
- `.eval` logs provide structured experiment tracking with `inspect view`
- OpenRouter is a first-class provider for quick calibration comparisons

### grader_prompt.py (kept as library)

The refactored `grader_prompt.py` is reused inside the Inspect Solver:
- `load_rubric()` — reads RUBRIC.md
- `build_system_prompt()` — constructs system prompt with rubric injection
- `_strip_rubric_for_prompt()` — removes docs-only sections before API injection
- `create_grading_prompt()` — formats title+abstract into user message

The Solver wraps these functions to construct `ChatMessage` objects for Inspect's `generate()`.

### Calibration testing (Task 3)

- Run updated grader on 25 calibration examples (`data/grader_calibration_examples.csv`)
- Compare across models (Gemini Flash, GPT-4o-mini, potentially Claude)
- Score: exact match on primary biomarker_use code, plus agreement rate across models
- Success criterion: <20% ambiguous/disagreement on these easy cases

### Hard case sampling (Task 4)

- Sample ~50 grants from the full dataset that do NOT contain explicit biomarker type terms (surrogate, pharmacodynamic, prognostic, predictive, etc.)
- These are grants matched by broader "biomarker" keyword but without self-labeling
- Manually review a subset to establish ground truth
- Test grader on these to measure robustness beyond easy cases

### Full dataset classification (Task 5)

- Classify all ~270K grants (title + abstract)
- Requires abstract data from `~/Downloads/RePORTER_PRJABS_C_FY*.zip` (FY2016 missing)
- Join abstracts to main dataset `data/nih_biomarker_unified_2004-2024.csv`
- Output: per-grant classification with all 3 dimensions + confidence + key phrases
- **Via Inspect**: `inspect eval-set --batch` with direct provider APIs (OpenAI, Google batch mode)

### Phased rollout

1. **Calibration** (25 examples): `inspect eval` with OpenRouter, fast iteration on rubric/prompt
2. **Mid-scale pass** (~10-20K grants, stratified by institute and year): `inspect eval` with direct provider APIs, `--max-connections 20`
3. **Full 270K production**: `inspect eval-set --batch` with OpenAI/Google batch APIs (50% cost savings)

## Decisions

- **grader_prompt.py reads RUBRIC.md at runtime** — rubric is single source of truth
- **Old hardcoded prompt preserved as `_LEGACY`** — reference only, not used in classification
- **Calibration before hard cases before full run** — fail fast on easy cases first
- **Inspect AI replaces hand-rolled scripts** — batch API, retry, caching, logging all built-in (Issue #7)

## Model Selection (Resolved 2026-03-02)

**3-model ensemble strategy:**

| Model | Role | Cost (270K grants) | Via |
|-------|------|--------------------|----|
| Gemini 2.5 Flash Lite | Primary grader #1 | ~$183 (~$92 with batch) | OpenRouter (calibration) / Google direct (production) |
| GPT-4.1-mini | Primary grader #2 | ~$275 (~$138 with batch) | OpenRouter (calibration) / OpenAI direct (production) |
| Claude Sonnet 4.6 | Tiebreaker (disagreements only) | ~$200-500 (~$100-250 with batch) | Anthropic Batch API |

**Total estimated cost: $350-480** with Inspect batch mode (was $700-900 via OpenRouter serial).

Note: GPT-4.1-mini replaces GPT-4o-mini (better instruction-following per OpenAI evals, 1M context).

Where the two cheap models disagree (~28% based on calibration), Sonnet adjudicates. This gives a natural reliability measure and surfaces hard cases.

**Why not Opus/Sonnet as primary?** Sonnet at $3/$15 per M tokens = ~$5,670 for one pass. Haiku 3.5 at $0.80/$4.00 = ~$1,300. Neither is competitive for structured classification where cheaper models perform adequately.

## Calibration Results (2026-03-02)

All 3 models tested on 25 easy cases (grants with explicit biomarker terms):

- **25/25 success** on all models (no parse errors, no API failures)
- **28% disagreement** on Dimension 1 (biomarker_use) between models
- Disagreements cluster on: pharmacodynamic vs surrogate_endpoint, stratification_treatment vs predictive_optimal, prognostic_risk vs prognostic_efficacy — exactly the rubric's harder distinctions
- Gemini models agree more with each other than with GPT-4o-mini

## Remaining Open Questions

- Whether FY2016 missing abstracts are acceptable or need alternative sourcing
- Ground truth labeling process for hard cases (Manjari manual review?)

## Inspect AI Reference (for future sessions)

Inspect is a **full grading pipeline**, not just an eval harness. Key capabilities:

- **Batch API**: `--batch` flag submits requests to provider batch APIs (OpenAI, Anthropic, Google) for 50% cost savings. Automatic batching, polling, result distribution.
- **Eval sets**: `inspect eval-set` runs across multiple models with automatic retry, sample preservation on interruption, resume on re-run.
- **Providers**: `openai/`, `anthropic/`, `google/`, `openrouter/` — all first-class. Batch mode works with direct provider APIs only (not OpenRouter).
- **Caching**: `--cache` avoids re-running identical prompts. Configurable expiry. Essential for rubric iteration.
- **Concurrency**: `--max-connections 20` for parallel async requests. Rate-limit detection with automatic backoff.
- **Logging**: `.eval` binary format (1/8 size of JSON), `inspect view` web UI, programmatic access via `read_eval_log()`.
- **Custom components**: `@solver` for prompt construction, `@scorer` for output evaluation, `@task` for composing them. `record_to_sample` for mapping CSV columns to Inspect's `Sample` objects.
- **Docs**: https://inspect.aisi.org.uk/ (batch: /models-batch.html, eval-sets: /eval-sets.html, providers: /providers.html, caching: /caching.html)
