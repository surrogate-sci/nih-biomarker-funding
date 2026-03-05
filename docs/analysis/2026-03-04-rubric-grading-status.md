# Rubric & Grading Status — 2026-03-04

## Current State

Three LLM models have graded a subset of ~2,000 NCI oncology grants (100/year × 20 years):

| Model | Grants graded | Errors | Status |
|-------|--------------|--------|--------|
| Gemini 2.5 Flash Lite | ~2,192 (in progress) | 6 | Completing |
| GPT-4o-mini | 233 | 20 (8.6%) | Abandoned — slow via OpenRouter |
| GPT-4.1-mini | 159 | 0 | Partial — stopped early |

## Model Agreement (N=139 triple-overlap)

| Dimension | Gemini vs 4o-mini | Gemini vs 4.1-mini | 4o-mini vs 4.1-mini | All 3 agree |
|-----------|:-:|:-:|:-:|:-:|
| Dim1 (biomarker use) | 63.9% | 67.9% | 69.1% | 54.0% |
| Dim2 (research design) | 55.8% | 70.4% | 60.4% | 49.6% |
| Dim3 (evidence strength) | 71.7% | 77.4% | 74.1% | 61.9% |

**GPT-4.1-mini agrees with Gemini more than GPT-4o-mini does** across all dimensions.

## Top Disagreement Patterns

### Dim1: Biomarker Use
- **`diagnostic` vs `susceptibility_risk`** (20-22% of disagreements): Gemini calls cancer screening/early detection `diagnostic`; OpenAI models call it `susceptibility_risk`. The rubric boundary is unclear for grants studying biomarkers in at-risk but disease-free populations.
- **`prognostic_risk` vs `prognostic_efficacy`** (6%): Ambiguity around whether a prognostic marker has treatment implications.
- **`methods_correlational` vs `methods_causal`**: Models disagree on whether computational/statistical methods grants are doing causal or correlational work.

### Dim2: Research Design
- **`observational_retrospective` vs `observational_cohort`** (45% of Dim2 disagreements): The single largest disagreement. "Retrospective analysis of banked specimens from a cohort study" — is it retrospective or cohort?
- **`experimental_singlearm` vs `experimental_rct`** (12%): Models disagree on whether a trial has a real control arm.

### Dim3: Evidence Strength
- **`correlational` vs `experimental_weak`** (27%): Threshold for what counts as "experimental."
- **`causal_preclinical` vs `experimental_weak`** (23%): Gemini is generous with `causal_preclinical` (30 vs 5 for GPT-4o-mini); GPT-4o-mini favors `experimental_weak`.
- **`methods_for_causal` vs `correlational`** (39% of Gemini vs 4.1-mini disagreements): Is a methods paper "for causal" or just correlational?

## Missing Rubric Categories (Manjari's observation)

Two biomarker use categories are absent from the current Dim1 codes:

1. **Biomarkers of efficacy / intermediate endpoints** — evidence the drug is doing what it's supposed to do, but short of surrogacy (not intended as a replacement for clinical endpoints)

2. **Target engagement biomarkers** — evidence the drug is reaching its mechanistic target and performing the immediate precondition steps, without needing to show disease/symptom reversal. Analogous to treatment compliance but for the drug's mechanism of action.

These sit in a gap between `pharmacodynamic` (biological response to intervention) and `surrogate_endpoint` (regulatory substitution for clinical endpoint).

## Disagreement Examples Extracted

40 examples (5 per pattern × 8 patterns) extracted to:
- `data/disagreement_examples.json` (structured, with per-model reasoning)
- `data/disagreement_examples.csv` (flat, for quick review)

These should be added to the expert review for rubric boundary calibration.

## Infrastructure Assessment

Current hand-rolled API scripts have known issues:
- No timeout on API calls (can hang indefinitely)
- No retry logic
- Checkpoint bug: error records treated as "done"
- Serial execution only
- No trace/result versioning

**Inspect AI** (UK AISI) is a strong fit for the production 270K run:
- Built-in batch API support (OpenAI, Anthropic, Google) = 50% cost savings
- Retry, timeout, rate limiting out of the box
- Checkpoint/resume that correctly handles errors
- Structured output via Pydantic schemas
- `.eval` log format with built-in viewer
- Our rubric/prompt maps cleanly to Inspect's task/solver/scorer model

## Recommended Next Steps

1. Expert reviews disagreement examples → sharpen rubric boundaries
2. Add missing Dim1 codes (efficacy biomarker, target engagement)
3. Migrate grading infrastructure to Inspect AI before 270K run
4. Set up trace storage/versioning for production runs
5. Re-run calibration with updated rubric to measure improvement
