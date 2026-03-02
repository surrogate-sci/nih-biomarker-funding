# Design: Rubric-Driven Grader Pipeline

**Date:** 2026-03-02
**Status:** In progress

## Problem

The LLM grader for classifying ~270K NIH biomarker grants needs:
1. A precise classification rubric (RUBRIC.md) — **done, pending review**
2. A grader that loads the rubric at runtime instead of hardcoding it
3. Calibration testing on known examples
4. Hard-case sampling for robustness testing
5. Full dataset classification

Previous Kosmos analysis had ~50% ambiguous classifications due to a binary causal/correlational schema and zero-shot prompting without a rigorous rubric.

## Architecture

```
data/RUBRIC.md          ← source of truth (17 + 10 + 5 codes)
        ↓
scripts/grader_prompt.py ← reads RUBRIC.md, constructs prompt, calls LLM API
        ↓
data/grader_calibration_examples.csv  ← 25 easy cases (explicit biomarker terms)
data/grader_hard_cases.csv            ← TBD, grants without explicit terms
        ↓
data/grader_results/                  ← per-model classification outputs
```

### grader_prompt.py refactor

Current state: SYSTEM_PROMPT contains a hardcoded copy of an older rubric with stale codes (`prognostic`, `risk`, `predictive_nonspecific`). OUTPUT_SCHEMA enum doesn't match current RUBRIC.md codes.

Target state:
- Read `data/RUBRIC.md` at runtime and inject into the system prompt
- OUTPUT_SCHEMA enum values match RUBRIC.md codes exactly
- Preserve the USER_PROMPT_TEMPLATE and API calling infrastructure
- Preserve test cases (update expected values to new codes)
- Keep the old hardcoded SYSTEM_PROMPT in a clearly marked `_LEGACY` variable for reference

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
- Batch processing with rate limiting and checkpointing

## Decisions

- **grader_prompt.py reads RUBRIC.md at runtime** — rubric is single source of truth
- **Old hardcoded prompt preserved as `_LEGACY`** — reference only, not used in classification
- **Calibration before hard cases before full run** — fail fast on easy cases first

## Open Questions

- Which LLM(s) to use for the full run (cost vs accuracy tradeoff at 270K scale)
- Whether FY2016 missing abstracts are acceptable or need alternative sourcing
- Ground truth labeling process for hard cases (Manjari manual review?)
