# Session: GPT Grading Run Completion, Haiku Tiebreaker Analysis, disease_non_biomarker — 2026-04-12

## State reference
- Code: branch `claude/silly-kare` @ `09a316d`
- Rubric: `data/RUBRIC.md` @ commit `8de20d3` (adds `disease_non_biomarker`; prior to this session it was @ `f6ecad8`)
- Calibration examples: `data/grader_calibration_examples.csv` @ commit `8de20d3` (48 rows; was 27 before this session)
- NCI grading runs (both complete):
  - Gemini: run `8erjM2hN9MQ5kE5LQvnP7L`, `logs/nci-v31-gemini-flash-lite/`, 3770/3770, rubric @ `f6ecad8`
  - GPT: run `hbNMjdEnGVXJ5YWcsKHfcQ`, `logs/nci-v31-gpt-oss-120b/`, 3770/3770, rubric @ `60d21e7`

*Both full NCI runs used the rubric WITHOUT `disease_non_biomarker` (added in `8de20d3` after the runs). See Open Questions.*

*Notes written against this state.*

---

## What we did

### Completing the full GPT grading run

At the start of this session, the Gemini full NCI run (run `8erjM2hN9MQ5kE5LQvnP7L`) had completed 3770/3770 samples. The GPT-OSS-120B run had died mid-session at 1508/3770 (run `YjUaR5DwUeHvnPUHm7gWFj`) because the `together/openai/gpt-oss-120b` model Inspect process was killed when the Claude Code session ended.

The root problem is that Inspect AI processes run as foreground processes attached to the terminal session. When a Claude Code session ends, any Inspect process it started is killed. Inspect does not support resuming partial runs — each invocation creates a new `.eval` file from scratch.

To decouple grading runs from Claude Code sessions, a new shell script `scripts/run-grading.sh` was created. The script calls `nohup ... &` to detach the Inspect process from the terminal, sources `.env` for API keys, auto-generates a log directory from the model name slug if not specified, and saves the process PID to `<log-dir>/inspect.pid` and stdout/stderr to `<log-dir>/inspect.log`. The first nohup launch attempt failed because the command string appended `disown` as a separate command after the background ampersand, which bash interpreted as a foreground command returning exit code 127. The nohup had already launched a process (PID 35355); a second launch was started immediately without the `disown`, and PID 35355 was killed. Both processes appear as separate runs in the manifest: `2erYYKhz22UPHDZJteNK3h` (killed at t=0) and `hbNMjdEnGVXJ5YWcsKHfcQ` (completed).

The completed GPT full run (`hbNMjdEnGVXJ5YWcsKHfcQ`, rubric @ `60d21e7`, no `--batch`) processed 3770/3770 samples with 0 errors, valid_json 99.9%, valid_codes 99.5%, total runtime 1:15:19, 23.4M tokens (19.9M input, 3.4M output). The Gemini full run stats are not available from a log file — the Gemini run was started before `run-grading.sh` was created and has no `inspect.log`.

### Haiku tiebreaker analysis on not_applicable disagreements

The 25-sample trial runs from the prior session had shown a major inter-model disagreement on `not_applicable` assignment: Gemini 2.5 Flash Lite assigned `not_applicable` to 0/25 grants; GPT-OSS-120B assigned it to 7/25. To determine which model was correct, 30 grants where the models disagreed on `not_applicable` vs. a biomarker code were sampled from the trial and partial-run outputs, and evaluated using Claude Haiku subagents (dispatched as 6 parallel batches of 5 grants each via the Agent tool). Each Haiku subagent reviewed the grant title and abstract against the rubric's Step 0 criteria and returned a classification judgment.

Haiku judged GPT-OSS-120B correct in 24/30 cases (80%). The common Gemini failure pattern was assigning biomarker codes (e.g., `susceptibility_risk`, `pharmacodynamic`, `stratification_diagnostic`) to grants conducting basic cancer biology or treatment research — studying disease mechanisms, developing targeted therapies, or optimizing treatment delivery — where a molecule, pathway, or assay was mentioned that has biomarker relevance in other contexts but was being investigated for its mechanistic or therapeutic role in these grants.

These Haiku judgments exist only in the conversation transcript; they were not saved as a standalone analysis artifact.

### disease_non_biomarker: new Dimension 1 code

The Haiku analysis revealed that the existing rubric's Step 0 had only two branches: infrastructure/support (`not_applicable`) and everything else (continue to Step 1). This meant there was no code for substantive disease research grants — basic cancer biology, treatment development, therapeutic optimization — that matched keyword screening but were not biomarker studies. These grants were being classified with whichever biomarker code seemed most plausible rather than being explicitly rejected at Step 0.

Manjari directed adding a new Dimension 1 code to cover this case. After two rounds of drafting and correction, the final `disease_non_biomarker` definition assigns to grants that are "substantive research on a disease — studying its biology, developing treatments, optimizing therapy delivery, or preventing it — but biomarker use is neither a primary aim nor a significant component of the research methodology."

Two drafting corrections were made by Manjari:

1. An initial draft included the sentence: "Grants developing targeted therapies or immunotherapies where a companion diagnostic or patient-selection biomarker is an inevitable component of the therapeutic strategy are NOT disease_non_biomarker." Manjari corrected this as too narrow — the exclusion from `disease_non_biomarker` is not limited to targeted therapy/companion diagnostic scenarios. The correct framing is: biomarker research is a "primary or significant component" when the grant uses biomarkers to investigate disease processes, discovers biomarkers or assay technologies, or applies a biomarker in any defined context of use (in any context, not limited to specific therapeutic strategies).

2. An initial draft used the phrase "developing, validating, or applying a biomarker in any of the defined contexts of use" for the exclusion criterion. Manjari corrected this as too narrow — biomarker research also includes biomarker discovery and assay technology development even outside the 20 coded Dim1 contexts.

The final definition adds a boundary clarification: "`disease_non_biomarker` is for grants conducting disease research in which biomarker use plays no primary or significant role" (distinct from `not_applicable`, which is for support infrastructure that is not itself conducting research).

Step 0 of the rubric was updated from two branches to three:
- Infrastructure or support → `not_applicable`. Stop.
- Disease research without a biomarker component → `disease_non_biomarker`. Stop.
- Biomarker research → continue to Step 1.

When `disease_non_biomarker` is assigned, Dimension 2 and Dimension 3 are null.

The `disease_non_biomarker` code is auto-detected from RUBRIC.md at import time by `inspect_task.parse_rubric_codes()`, requiring no hardcoded changes to the task. The `VALID_DIM1` set grew from 20 to 21 codes; `tests/test_inspect_task.py` line 165 (`TestCodeEnums.test_dim1_count`) was updated from `assertEqual(len(VALID_DIM1), 20)` to `assertEqual(len(VALID_DIM1), 21)`. All 45 tests pass.

### Calibration CSV: 21 Haiku-confirmed examples added

Twenty-one rows were appended to `data/grader_calibration_examples.csv` (file previously at 27 rows, now 48). All 21 grants are sourced from `data/nci_sample_v31_seed42.csv` (FY2015–2022, CA grants). Grant abstracts were available from that CSV (which includes `ABSTRACT_TEXT`). `GOLD_DIM2` and `GOLD_DIM3` were left blank for all 21 rows.

17 grants labeled `GOLD_DIM1 = disease_non_biomarker`:
- 7360310 (Fra-1 transcription factor vaccine for metastatic cancer)
- 6787640 (colorectal cancer prevention by fiber diet and calcium)
- 8906783 (gold nanoparticles for drug delivery in prostate cancer)
- 7756608 (STAT3 targeting in HNSCC tumor stroma)
- 7655398 (antibody-targeted radiation for lymphoma)
- 7458255 (cytotoxic agents in combination chemotherapy for pancreatic cancer)
- 8899459 (MUC1 peptide immunotherapy for pancreatic cancer)
- 7287699 (Sleeping Beauty transposon T-cell therapy for B-cell lymphomas)
- 8764593 (autophagy modulation in cancer treatment)
- 8382809 (mitochondrial uncoupling agents for chemotherapy sensitization)
- 7270579 (intensity-guided IMRT for salivary gland protection in head and neck)
- 8555135 (thermal ablation dose-response in cancer treatment)
- 8157725 (HSCT relapse reduction strategies)
- 6832324 (geostatistical software for radiation dosimetry — infrastructure)
- 7277177 (institutional NCI-designated Cancer Center immunotherapy program)
- 7650821 (myeloma anti-tumor immunity by vaccine)
- 7667687 (TeleCare Consortium — patient support program)

4 grants labeled `GOLD_DIM1 = not_applicable` (support infrastructure):
- 8689919 (Biomarkers Scientific Collection Core at Fred Hutch)
- 8288255 (epigenetics laboratory services core)
- 8327267 (TCGA Genome Data Analysis Center — GDAC — bioinformatics infrastructure)
- 7944141 (CER quantitative imaging resource core)

The 21 examples were identified from the Haiku tiebreaker analysis (see above). The labels are researcher-confirmed via Manjari's approval of the examples after reviewing them; they are not independently sourced from a prior publication or benchmark.

### Manifest cleanup

An audit of all `.eval` files on disk against `logs/manifest.csv` found three discrepancies:
1. Run `3GsA5wAQoa2zUi59KsBQxU` was recorded with a typo (`3GsA5wAQoazUi59KsBQxU`, missing the `2`) in both `run_id` and `log_path`.
2. Run `F6q3hinVzvzWqqjLCnoL28` (`logs/test-nci-filter/`, April 7 2026, 3 samples, Gemini, rubric `c4b99b3`) was absent from the manifest.
3. Run `eUp5oWXd9G3cRfUDdvAW8w` (`logs/test-nci-verify/`, April 7 2026, 5 samples, Gemini, rubric `c4b99b3`) was absent from the manifest.

All three were corrected (commit `09a316d`). The reason fields for the two missing entries ("3-sample filter test", "5-sample verify test") are inferred from directory names; no `inspect.log` exists in either directory to confirm the descriptions.

---

## Key decisions

1. **nohup in run-grading.sh rather than screen/tmux** — `screen` is available on the system without installation; `tmux` would require `brew install`. nohup was chosen as simpler for non-interactive detached background jobs; screen/tmux remain options when interactive monitoring of the process is needed. Researcher approved the approach.

2. **disease_non_biomarker applies when biomarker use is neither primary nor a significant component** — The threshold is intentionally broad: it covers discovery, assay technology development, and any defined context of use in any direction. The focus is on whether the grant's research activity is structured around a biomarker rather than around disease biology or treatment. Researcher set this threshold through two correction rounds.

3. **Both full NCI grading runs completed before disease_non_biomarker was added to the rubric** — The Gemini run (rubric `f6ecad8`) and GPT run (rubric `60d21e7`) both predate the `disease_non_biomarker` addition (`8de20d3`). The new code was developed based on findings from those runs but not applied to them. Researcher is aware; downstream analysis will need to account for this.

4. **21 calibration examples are gold-labeled by researcher approval** — Manjari approved the examples after reviewing the Haiku-suggested classifications. As with the NRG/WashU TDD examples from the prior session, these are not sourced from a prior published benchmark.

---

## Corrections received

- **CDx framing too narrow** → The initial exclusion from `disease_non_biomarker` was written as specific to targeted therapy/companion diagnostic contexts. Correct understanding: the exclusion applies whenever biomarker use is a primary or significant component in any context, including discovery, assay development, and mechanistic investigation — not limited to any particular therapeutic strategy.

- **"Defined contexts of use" too narrow** → Initial phrasing "developing, validating, or applying a biomarker in any of the defined contexts of use" implied the 20 coded Dim1 contexts were exhaustive. Correct understanding: biomarker research extends to any context where a biomarker is a primary or significant methodological component, including uses not captured by the 20 coded contexts.

---

## Open questions

- **Full NCI runs use pre-disease_non_biomarker rubric**: Both completed runs (`8erjM2hN9MQ5kE5LQvnP7L` Gemini, `hbNMjdEnGVXJ5YWcsKHfcQ` GPT) scored against a rubric without `disease_non_biomarker`. Grants that should now be classified as `disease_non_biomarker` are instead distributed across biomarker codes (likely `susceptibility_risk`, `pharmacodynamic`, `stratification_diagnostic`, `not_applicable`). Should these runs be re-scored using Inspect's deferred scoring (`inspect score`) with the updated rubric? Or does the plan call for new grading runs on the full sample? Requires researcher judgment before proceeding to cross-model agreement analysis.

- **Haiku tiebreaker data not persisted**: The 30-grant Haiku review output (which grants were reviewed, which was judged GPT-correct vs. Gemini-correct, and the reasoning) exists only in the conversation transcript at `/Users/mnarayan/.claude/projects/-Users-mnarayan-Documents-Coding-Cloud-nih-biomarker-funding--claude-worktrees-silly-kare/def30b42-9ee0-47ac-9d96-651097e5cd8a.jsonl`. If needed for reference (e.g., to identify which grants informed the rubric definition), it can be extracted from that transcript.

- **Inter-model agreement on full 3770-grant NCI sample**: The 25-sample trials showed dramatic disagreement (0% vs. 28% `not_applicable` between Gemini and GPT). This disagreement structure should now be analyzed at full scale — but the rubric mismatch (pre- vs. post-`disease_non_biomarker`) complicates direct comparison.

- **Gemini full run stats unavailable**: The Gemini full run (`8erjM2hN9MQ5kE5LQvnP7L`) was started before `run-grading.sh` existed, so there is no `inspect.log` recording valid_json/valid_codes rates or token counts. Stats would require parsing the `.eval` file directly via `scripts/analyze_eval_results.py`.

---

## Next steps

- Decide whether to re-run or re-score both NCI grading runs with the updated rubric (adding `disease_non_biomarker`). Options: (a) new `inspect eval` calls with rubric `8de20d3`; (b) `inspect score` deferred re-scoring if the scorer accepts the new code without regenerating outputs.
- Compute inter-model agreement on full NCI sample (3,770 grants) once the rubric question above is resolved.
- Extract Gemini full run stats from `logs/nci-v31-gemini-flash-lite/2026-04-12T15-06-44-00-00_biomarker-grading_8erjM2hN9MQ5kE5LQvnP7L.eval` using `scripts/analyze_eval_results.py`.
- Plan sensitivity analysis (Issue #20) before scaling to 270K-grant full pilot.

---

## Files created/updated

- `data/RUBRIC.md` — Added `disease_non_biomarker` Dim1 code; updated Step 0 to three branches (commit `8de20d3`)
- `data/grader_calibration_examples.csv` — Appended 21 rows (17 `disease_non_biomarker`, 4 `not_applicable`) (commit `8de20d3`)
- `tests/test_inspect_task.py` — Updated `test_dim1_count` from 20 to 21 (commit `8de20d3`)
- `scripts/run-grading.sh` — New script: nohup-based Inspect eval launcher, session-independent, logs to `<log-dir>/inspect.log` (committed this session)
- `logs/manifest.csv` — Added 6 rows total (4 this session's grading runs, 2 missing April 7 entries); fixed 1 run_id/log_path typo (commits `8de20d3`, `09a316d`)
