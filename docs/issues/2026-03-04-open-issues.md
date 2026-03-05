# Open Issues — 2026-03-04

## Rubric Issues

### R1: Sharpen `diagnostic` vs `susceptibility_risk` boundary
**Priority: High** | Dim1 | 20-22% of all Dim1 disagreements

Gemini assigns `diagnostic` where OpenAI models assign `susceptibility_risk` for cancer screening/early detection grants — biomarkers in at-risk but disease-free populations. 26 disagreements out of 253 multi-model grants. 5 examples extracted in `data/disagreement_examples.json`.

### R2: Sharpen `observational_retrospective` vs `observational_cohort` boundary
**Priority: High** | Dim2 | 45% of Gemini-vs-4o-mini Dim2 disagreements

"Retrospective analysis of banked specimens from a cohort study" — is it retrospective or cohort? 54 disagreements. The single largest disagreement pattern.

### R3: Clarify `causal_preclinical` vs `experimental_weak` vs `correlational` thresholds
**Priority: High** | Dim3 | Systematic model-level bias

Gemini is generous with `causal_preclinical` (30 vs 5 for GPT-4o-mini on N=139); GPT-4o-mini favors `experimental_weak` (36 vs 16 for Gemini). This isn't random noise — it's a systematic difference in how models interpret the evidence strength threshold.

### R4: Add missing Dim1 code — biomarkers of efficacy / intermediate endpoints
**Priority: Medium** | Dim1 | Missing category

Evidence the drug is doing what it's supposed to do, but short of surrogacy. Not intended as replacement for clinical endpoints. Currently no code captures this — grants fall ambiguously between `pharmacodynamic` and `surrogate_endpoint`. (Manjari's observation)

### R5: Add missing Dim1 code — target engagement biomarkers
**Priority: Medium** | Dim1 | Missing category

Evidence the drug is reaching its mechanistic target and performing immediate precondition steps, without needing to show disease/symptom reversal. Treatment compliance equivalent for drug mechanism. (Manjari's observation)

### R6: Clarify `methods_correlational` vs `methods_causal`
**Priority: Medium** | Dim1 | 7 disagreements

Models disagree on whether computational/statistical methods grants are doing causal or correlational work. Need clearer "Assign when..." criteria.

### R7: Clarify `experimental_singlearm` vs `experimental_rct`
**Priority: Low** | Dim2 | 13 disagreements

Models disagree on whether a trial has a real control arm. May be an abstract ambiguity issue rather than a rubric issue.

### R8: Clarify `methods_for_causal` vs `correlational`
**Priority: Medium** | Dim3 | 39% of Gemini-vs-4.1-mini Dim3 disagreements

Is a methods paper "for causal" or just correlational? The intent-vs-output distinction needs sharpening.

## Infrastructure Issues

### I1: Migrate grading pipeline to Inspect AI
**Priority: High** | Before 270K production run

Current hand-rolled scripts have: no timeout, no retry, checkpoint bug (errors treated as "done"), serial execution only. Inspect AI provides all of this plus batch API support (50% cost savings = ~$350-450 on the full run). See Inspect research in session notes.

### I2: Set up trace storage / versioning
**Priority: Medium** | Before production run

Currently grades are JSONL files with no versioning. Need to decide: Inspect's `.eval` logs vs W&B vs OpenRouter's built-in logging. Key requirements: version results across rubric iterations, compare runs, store model reasoning.

### I3: Execute codebase cleanup plan
**Priority: Medium** | PR-ready

7-task plan at `docs/plans/2026-03-04-codebase-cleanup-and-api-architecture.md`. Extract shared utils, fix API bugs, slim `grader_prompt.py`, remove dead code, stage new scripts, update docs.

### I4: Update CLAUDE.md with current project state
**Priority: Low** | After cleanup PR

GPT-4o-mini → GPT-4.1-mini, add new scripts to Key Files, update status line.
