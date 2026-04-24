# Session: Rubric Expansion and Pilot Sample Release — 2026-04-07

## What we did
Expanded RUBRIC.md with three new Dim1 codes (`not_applicable`, `target_engagement`, `efficacy_biomarker`), wired up Inspect AI pipeline with manifest logging, moved the pilot sample (59MB) out of git and into the GitHub release, and completed download-dataset.sh to fetch both files.

## Key decisions

1. **`not_applicable` as Dim1 code** — Grants that matched keyword screening but are not substantively about biomarker research (infrastructure, admin cores, etc.) get `not_applicable`; Dim2 and Dim3 are left null. Scorer skips enum validation for those dimensions when `not_applicable` is assigned. Treats false-positive keyword matches as a classification outcome rather than a pre-filter problem.

2. **`target_engagement` definition** — Biomarker used to confirm intervention reached its intended site of action. Intentionally avoids hardcoding modality (non-pharmacological interventions like brain stimulation can have both target engagement and PD evidence from the same measure). Key distinction from `pharmacodynamic`: inferential purpose, not in-vivo vs in-vitro modality. Manjari corrected an earlier draft that tried to distinguish by modality.

3. **`efficacy_biomarker` definition** — Evidence of reversal/amelioration of a pathological process. Causal role of the disease biomarker need **not** be definitively established — in psychiatry, treatment-induced change is used as reverse inference about disease etiology (this is valid efficacy biomarker use). Initial draft required "firmly established" causal role; Manjari corrected this as too strong.

4. **Pilot sample moved to `dataset-release-v3.1`** — File was 59MB, exceeded GitHub's 50MB recommendation. Should have been caught before the first push; wasn't flagged proactively (correction received). SHA256 in download-dataset.sh: `3db257e5776bdf35176837e0dc4d2edb29d736e9845362b78d67b49b86add6c6`.

5. **Manifest hook in settings.local.json** — PostToolUse hook injects `additionalContext` reminding to append a row to `logs/manifest.csv` after any `inspect eval` bash call. Schema filed as Issue #41.

## Corrections received

- **Large file not flagged proactively** → Always check file size before pushing; warn if >50MB before committing, not after.
- **GOOGLE_API_KEY override** → Manjari never set `GOOGLE_API_KEY`; only `GEMINI_API_KEY` is in `.env`. Remove any `GOOGLE_API_KEY="${GOOGLE_API_KEY:-$GEMINI_API_KEY}"` shim; use `export $(grep -v '^#' .env | xargs)` directly.
- **`efficacy_biomarker` "too strong"** → Dropped requirement for disease biomarker causal role to be "firmly established"; softer framing handles psychiatry reverse-inference use case.
- **Target engagement modality** → Don't distinguish `target_engagement` from `pharmacodynamic` by in-vitro/in-vivo modality; use inferential purpose instead (confirmed by Manjari after back-and-forth).

## Open questions

- **Issue #5 (Dim3 thresholds)**: `causal_preclinical` vs `experimental_weak` vs `correlational` — model disagreement pattern, not yet addressed.
- **Second grader for NCI run**: GPT-OSS-120B (Meta-Llama-3.3-70B-Instruct-Turbo on Together AI) was discussed but needs `TOGETHER_API_KEY` added to `.env` before testing. 5-grant test on both Gemini and Together not yet run.

## Next steps

1. Add `TOGETHER_API_KEY` to `.env` (Manjari) and run 5-grant smoke test on Together AI model
2. Create `data/nci_sample_v31_seed42.csv` (filter pilot to CA grants only)
3. Run full NCI grading: `inspect eval inspect_task.py -T dataset_path=data/nci_sample_v31_seed42.csv --model google/gemini-2.5-flash-lite --temperature 0.0 --batch`
4. Address Issue #5 (Dim3 thresholds) before or alongside NCI run

## Files created/updated

- `data/RUBRIC.md` — Added `not_applicable`, `target_engagement`, `efficacy_biomarker` to Dim1; updated `pharmacodynamic` and `surrogate_endpoint` distinguish-from clauses; updated mapping table; added Step 0 to Decision Hierarchy
- `inspect_task.py` — Default `dataset_path` changed to pilot sample; `_validate_codes()` skips Dim2/Dim3 when `not_applicable`
- `scripts/download-dataset.sh` — Adds pilot sample download + SHA256 verification; updates early-exit to check both files
- `scripts/sample_grants.py` — Min floor changed from 25 → 50
- `scripts/legacy/` — Moved `run_batch_grading.py`, `run_calibration.py`, `analyze_agreement.py`, `extract_disagreements.py`
- `data/march-pilot-nci-2k/` — Archived 14 files from March 2026 pilot
- `CLAUDE.md` — Added manifest reminder rule, updated Key Files and Commands
- `.claude/settings.local.json` — PostToolUse manifest hook, google-genai and venv inspect path permissions
- `requirements.txt` — Added `google-genai`, `openai`
- `logs/manifest.csv` — Created; first entry is smoke test run
- `data/pilot_sample_12IC_tiered_seed42.csv` — Removed from git (`git rm --cached`); now in `dataset-release-v3.1`
