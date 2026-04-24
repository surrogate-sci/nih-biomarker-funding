# Session: NCI Sample Regeneration, P30 Filter, Rubric Sharpening, Grading Re-run — 2026-04-12

## State reference
- Code: branch `claude/silly-kare` @ `ebe59f0`
- Rubric: `data/RUBRIC.md` as of commit `f6ecad8` (sharpen `not_applicable` — support-for vs conducting)
- Calibration examples: `data/grader_calibration_examples.csv` @ commit `0ee944c` (27 rows, 2 new TDD boundary cases)
- Pilot sample: `data/pilot_sample_12IC_tiered_seed42.csv` — regenerated this session (20,644 grants), on GitHub release `dataset-release-v3.1` (clobbered prior 21,424-row version — see Key Decisions)
- NCI sample: `data/nci_sample_v31_seed42.csv` — regenerated this session (3,770 grants), CA subset of pilot sample, on GitHub release `dataset-release-v3.1`
- Eval runs in progress: full NCI grading for `google/gemini-2.5-flash-lite` and `together/openai/gpt-oss-120b`, both without `--batch`, log dirs `logs/nci-v31-gemini-flash-lite/` and `logs/nci-v31-gpt-oss-120b/`

*Notes written against this state. Grading runs had not completed at time of writing.*

---

## What we did

### Starting point: context-rotted prior session

The April 7 session had attempted to launch grading runs on the NCI sample but left several things broken: the `data/nci_sample_v31_seed42.csv` had been force-added to git (should live on the GitHub release like the pilot sample), `scripts/sample_grants.py` had context-rotted changes (`--exclude-activities` and `--rate-multiplier` parameters without a proper spec), and `tests/test_inspect_task.py` had test classes that did not inherit from `unittest.TestCase`, causing `python3 -m unittest` to find 0 tests. Both grading runs from April 7 had failed: Gemini failed with `400 INVALID_ARGUMENT` from the Gemini batch API (format incompatibility — Inspect sends JSON arrays where Google's batch endpoint expects objects), and GPT-OSS-120B via Together AI was killed mid-session at 421/4,210 samples. Two further attempts on April 8 to use Together's native batch API both failed: first due to a missing `pip install together` dependency, then due to Together's batch endpoint rejecting OpenAI-format JSONL (the format Inspect's Together provider generates).

### Rubric update: sharpening `not_applicable`

The prior session had identified that two NCI grants — the NRG Oncology Biospecimen Bank (APPLICATION_ID 8912013, FY2015, CA, U24) and the Washington University Co-Clinical Imaging Research Resource (APPLICATION_ID 9296276, FY2017, CA, U24) — were being scored as `predictive_enrichment` by both Gemini and GPT-OSS-120B. The NRG Oncology Biospecimen Bank banks tumor specimens for other investigators' biomarker studies; it does not conduct biomarker research itself. The WashU imaging resource develops and validates quantitative imaging biomarkers (quantitative MRI, PET, CT) for use in co-clinical trials — it does conduct biomarker research. Manjari confirmed that the NRG case is a false positive (should be `not_applicable`) and the WashU case is a true positive (should be `predictive_enrichment`).

The existing `not_applicable` definition did not distinguish between grants that provide support infrastructure for biomarker studies versus grants that conduct biomarker research. A clarifying paragraph was added (commit `f6ecad8`):

> The key distinction is whether the grant is *providing support for* biomarker studies versus *conducting* them. Grants whose primary purpose is specimen banking, data distribution, coordinating infrastructure, or administrative management of a network — where the biomarker work is done by other investigators using the resources — assign `not_applicable`. Grants that conduct actual biomarker research, including technology or measurement development to develop or validate biomarkers (e.g., developing and validating quantitative imaging methods as biomarkers, even when funded through a shared-resource mechanism), do NOT assign `not_applicable`.

### TDD boundary test cases added to calibration CSV

Two rows were appended to `data/grader_calibration_examples.csv` as internal TDD development examples for agentic rubric checking (commit `0ee944c`). These are not external benchmark gold labels — Manjari sets those only when explicitly flagging them. The `GOLD_DIM1`, `GOLD_DIM2`, and `GOLD_DIM3` columns were added to the CSV header (all existing rows left blank for those columns).

- NRG Oncology Biospecimen Bank (app_id 8912013, FY2015, CA, U24): `GOLD_DIM1 = not_applicable`
- WashU Co-Clinical Imaging Resource (app_id 9296276, FY2017, CA, U24): `GOLD_DIM1 = predictive_enrichment`

Abstracts were loaded from `~/Downloads/RePORTER_PRJABS_C_FY2015.zip` and `~/Downloads/RePORTER_PRJABS_C_FY2017.zip` respectively. Both rows load correctly via `inspect_task.record_to_sample()` with correct `Sample.target` values.

### P30 filter: design and implementation

The prior session had explored the activity code composition of the NCI biomarker grants pool. P30 grants are Cancer Center Support Grants (core infrastructure grants that fund shared resources, administrative cores, and data management for NCI-designated cancer centers). With 8,779 CA P30 grants in the unified dataset, they form a substantial fraction of the pool. Many match biomarker keyword screening because cancer center cores describe the broader research portfolio; they do not themselves conduct biomarker research.

The filter implemented: P30 grants are excluded from sampling unless `NIH_SPENDING_CATS` contains the string "clinical" (case-insensitive). The `NIH_SPENDING_CATS` column lists NIH spending category tags for each grant; grants tagged with clinical categories (e.g., "Clinical Research") are retained regardless of activity code.

One design consideration was whether to also filter other activity codes (U-series infrastructure grants, T32 training grants, etc.). Spot-checking with Haiku subagents during the prior session confirmed that U24, U19, and U2C grants in the biomarker pool are generally substantive biomarker research (not just infrastructure), even when funded under coordinating mechanisms. T32 training grants contain genuine biomarker research conducted by trainees. Only P30 was identified as reliably infrastructure-heavy enough to warrant blanket filtering with the clinical override.

Pre-2008 grants often have empty `NIH_SPENDING_CATS` (the column was not consistently populated in early NIH ExPORTER releases). P30 grants with empty spending cats are excluded by this filter — the clinical override does not fire. This is a known limitation: some early P30 clinical trials grants (e.g., ECOG/NSABP coordinating centers) may be incorrectly excluded.

Implementation in `scripts/sample_grants.py` was done via TDD (commit `d8c7b35`): six tests in a new `TestLoadGrantsP30Filter` class were written first and verified to fail before implementing the filter. All 14 tests in `tests/test_sample_grants.py` pass.

### Fixing test_inspect_task.py

All five test classes in `tests/test_inspect_task.py` used pytest-style bare `assert` statements without inheriting from `unittest.TestCase`. Running `python3 -m unittest tests.test_inspect_task` reported `Ran 0 tests in 0.000s`. All classes were converted to `unittest.TestCase` with `self.assert*` methods (commit `4782f4a`). During conversion, the `test_dim1_count` assertion was updated from 17 to 20 to reflect three codes added to Dimension 1 since the test was written: `not_applicable` (commit `0d8395c`), `target_engagement`, and `efficacy_biomarker` (commit `2210cdf`). All 31 tests now pass.

### Pilot sample regeneration with P30 filter

The full 12-IC pilot sample (`data/pilot_sample_12IC_tiered_seed42.csv`) was regenerated to apply the P30 filter. Key parameters: 12 ICs (CA, HL, AG, AI, NS, MH, DK, HD, GM, DA, EB, AR), tiered sampling rates (5% CA, 7% ICs ≥20K grants, 10% smaller ICs), seed 42, 50-grant floor per FY stratum. FY2016 abstracts, previously believed missing, were found to be present in `~/Downloads/RePORTER_PRJABS_C_FY2016.zip` (58MB, 1,024 NCI grants covered) and were included.

Results:
- 14,260 P30 grants excluded across 12 ICs (vs. 0 in prior version)
- Pool: 271,897 grants (was ~286K)
- Sampled: 20,644 grants (was 21,424; decrease of 780 due to P30 exclusions)
- Abstracts joined: 20,427/20,644 (99% coverage)

The NCI sample was then extracted as the CA-only subset: 3,770 grants (was 4,210; decrease of 440 CA P30 exclusions). Both files were uploaded to GitHub release `dataset-release-v3.1` with `--clobber` (overwriting prior versions), and `scripts/download-dataset.sh` was updated with new SHA256 values (pilot: `5824dc824a84b937...`, NCI: `f5a6baa932d88129...`). Note: `nci_sample_v31_seed42.csv` was removed from git tracking (`git rm --cached`) — it now lives only on the release, consistent with the pilot sample.

### Confirm inspect saves rubric and prompt

Inspect AI `.eval` files are journal-based ZIP archives. The `_journal/start.json` entry contains the full eval configuration including task arguments (which include `dataset_path`) and solver configuration. The system prompt — built by `scripts/grader_prompt.py:build_system_prompt()` from the contents of `data/RUBRIC.md` at run time — is embedded in the solver's message list in the start journal entry. This means the rubric text is preserved in every `.eval` file and is recoverable even if `data/RUBRIC.md` is later modified.

### Batch API status: confirmed structural failures

Four trials with `--batch` were run this session (in addition to two prior batch attempts in April 7–8):

- `google/gemini-2.5-flash-lite --batch`: `400 INVALID_ARGUMENT` — Inspect AI's Google batch provider constructs batch files with JSON arrays (`[...]`) where Google's batch API requires JSONL with top-level objects. This is a bug in the installed version of `inspect_ai`'s Google provider (version not yet confirmed), not a transient error. All 25 requests failed before reaching the model.
- `together/openai/gpt-oss-120b --batch`: Together AI's batch file validator rejects OpenAI-format JSONL (fields `custom_id`, `method`, `url`, `body`) with `FileTypeError: Could not detect a format`. Together's batch endpoint expects its own native schema. Fundamental incompatibility, not transient.

Both models run cleanly without `--batch` via their respective synchronous/streaming completions endpoints. Trial runs (25 samples each, no `--batch`) completed 25/25 with 100% valid_json and 96% valid_codes (1 invalid dim2 code each).

### Inter-model not_applicable disagreement observed in trials

On the same 25-grant trial sample from `data/nci_sample_v31_seed42.csv`:
- `google/gemini-2.5-flash-lite`: 0% `not_applicable` (0/25)
- `together/openai/gpt-oss-120b`: 28% `not_applicable` (7/25)

This is a notable inter-model disagreement on the exact dimension the rubric was sharpened for this session. Whether this reflects Gemini under-assigning or GPT over-assigning `not_applicable` requires review of the specific grants involved. The full 3,770-grant runs (in progress at time of writing) will provide a larger sample for comparing the distributions.

---

## Key decisions

1. **Filter only P30, not other activity codes** — Researcher direction after reviewing U24/U19/U2C examples. Those grants are substantive biomarker research even under shared-resource/coordinating mechanisms. Only P30 (Cancer Center Support Grants) was identified as reliably infrastructure-heavy.

2. **Keep the clinical override for P30** — P30 grants with `NIH_SPENDING_CATS` containing "clinical" are retained. Covers P30-supported clinical trial infrastructure that touches biomarker measurements. Researcher confirmed.

3. **Subselect NCI from full pilot, not run CA-only** — The NCI sample must be derived as the CA subset of the full 12-IC pilot sample, not generated by running the sampler with `--ics CA` alone. Researcher corrected this mid-session.

4. **Clobbered v3.1 release assets** — Both updated files (pilot sample, NCI sample) were uploaded with `--clobber` to `dataset-release-v3.1`, overwriting prior versions. Researcher confirmed overwrite was acceptable for this case but noted that in future, derived file changes should use a new minor release tag (e.g., `dataset-release-v3.2`) rather than overwriting.

5. **TDD calibration examples are internal development set only** — Not external benchmark gold labels. Researcher explicitly clarified: gold labels are set only when Manjari explicitly flags them. The `GOLD_DIM1` entries for NRG/WashU are agentic TDD checkpoints for rubric development, not a scored evaluation benchmark.

---

## Open questions

- **Not_applicable inter-model disagreement**: GPT-OSS-120b assigned `not_applicable` to 28% of the 25-trial grants while Gemini assigned 0%. Needs review: are GPT's `not_applicable` assignments correct under the sharpened rubric, or is the rubric clarification insufficient to close the gap? Requires researcher review of the specific GPT `not_applicable` examples.

- **Batch API fix path**: Both `--batch` modes fail due to structural incompatibilities in `inspect_ai`'s provider implementations. Should we file an issue against `inspect_ai`? Check whether a newer version has fixed either? The non-batch path is viable at 3,770-grant scale but will be slower/more expensive at 270K-grant scale.

- **Early-year P30 clinical grants**: Pre-2008 grants often have empty `NIH_SPENDING_CATS`, so the clinical override does not fire even for genuine clinical P30 grants (e.g., early ECOG/NSABP cooperative group center grants). Extent of impact not quantified.

---

## Next steps

- Review full grading results when runs complete: check `not_applicable` rates per model, valid_json/valid_codes rates, Dim1 distribution
- Pull GPT-OSS-120b `not_applicable` examples from the 25-sample trial (run IDs in manifest) and review against the sharpened rubric definition
- Compute inter-model agreement on the full 3,770-grant NCI sample once both runs complete
- Decide whether to proceed to 270K-grant full pilot grading or run additional calibration/sensitivity analysis first (Issue #20)
- Address the clobbered release: consider tagging a new `dataset-release-v3.2` for future derived-file updates

---

## Files created/updated

- `data/RUBRIC.md` — `not_applicable` definition expanded with support-for vs conducting paragraph (commit `f6ecad8`)
- `data/grader_calibration_examples.csv` — Added `GOLD_DIM1/2/3` columns, appended 2 TDD boundary rows (NRG, WashU) (commit `0ee944c`)
- `tests/test_inspect_task.py` — Converted all 5 classes to `unittest.TestCase`; updated Dim1 count from 17→20 (commit `4782f4a`)
- `scripts/analyze_eval_results.py` — New script: reads journal-based `.eval` ZIP archives without EOCD, extracts per-sample scores and dimension distributions (commit `125b09b`)
- `scripts/sample_grants.py` — Added P30 filter in `load_grants()` (commit `d8c7b35`)
- `tests/test_sample_grants.py` — Added `TestLoadGrantsP30Filter` with 6 TDD tests (commit `d8c7b35`)
- `data/nci_sample_v31_seed42.csv` — Removed from git tracking; now on GitHub release only (commit `f6db6cd`)
- `scripts/download-dataset.sh` — Added NCI sample download block; updated SHA256 for pilot (new: `5824dc...`) and NCI (new: `f5a6ba...`) (commits `903c07e`, `ebe59f0`)
- `CLAUDE.md` — Updated pilot sample row count (20,644), added NCI sample entry
- `logs/manifest.csv` — Added 4 rows for this session's runs (2 successful trials, 2 batch failures)
