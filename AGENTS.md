# NIH Biomarker Funding Analysis

Agent instructions for this repo (Claude Code, Codex, Cursor, and others). `CLAUDE.md` imports this file.

## Project Goal

Produce data for a policy-level blog post (target venues: Good Science Project, IFP,
Clinical Trial Abundance) supporting or refuting the hypothesis that most NIH biomarker
funding operates without a clear estimand (causal or decision-theoretic), and that
surrogacy/mechanistic validation is an afterthought rather than a design consideration.

The pipeline: keyword-filter 20 years of NIH ExPORTER data into ~270K biomarker grants,
then LLM-grade each on 3 dimensions (biomarker use, research design, evidence strength)
using a custom rubric that extends FDA-NIH BEST to capture the gradient of specificity
in how researchers invoke biomarker concepts.

**Prior art**: The Edison analysis agent (`../edison-benchmarks/`) produced a poor rubric
with ~50% ambiguous classifications. This repo replaces that with a hand-designed rubric.

## Session Setup

- **Skills bootstrap**: If `.claude/skills/using-superpowers/SKILL.md` doesn't exist, run `bash scripts/download-skills.sh` to download obra/superpowers skills. This is needed in environments without access to user-level skills (e.g., mobile Claude Code sessions).
- **Dataset download**: If `data/nih_biomarker_unified_2004-2024.csv` doesn't exist, run `bash scripts/download-dataset.sh`. Requires `gh` auth or `GITHUB_TOKEN` env var (private repo).
- **Skills are plain files**: Claude Code loads `.claude/skills/*/SKILL.md` automatically. Other agents should open the relevant `SKILL.md` and follow it, especially `.claude/skills/grading-run/SKILL.md` before any grading run.

## Rules

- **RUBRIC.md is scientific content** — do not modify definitions without Manjari's explicit direction
- **"I draft, you correct" workflow** — Manjari dictates scientific substance; the agent organizes/formats
- **Manjari edits concurrently in Cursor** — check for file modifications before overwriting; preserve her changes
- **Refactoring/cleanup → PR** (not direct commit to main). Doc updates → direct commit is fine.
- **`data/` and `logs/` are gitignored** — use `git add -f` for tracked files (RUBRIC.md, calibration CSVs, `logs/manifest.csv`, results)
- **Commit style**: imperative, scoped prefix: `grade: calibrate rubric`, `fetch: add sharder`
- **Don't use**: `_archive/`, `../edison-benchmarks/`, old skill dirs
- **Don't invent scientific positions** — never paraphrase domain claims or add causal language Manjari didn't provide
- **After every `inspect eval` / `inspect score` run** — append a row to `logs/manifest.csv` before moving on (schema: Issue #41; procedure: `.claude/skills/grading-run/SKILL.md`)
- **Log folders are named for humans**: `logs/YYYY-MM-DD_<sample>-<n>_<models>[_<purpose>]/`, e.g. `logs/2026-11-06_nci-3718_opus-sonnet-5.5/`. Rubric and code commits go in the manifest, not in folder names.
- **Never overwrite or delete paid `.eval` logs** — re-score into a new folder with `inspect score --output-file`
- **GitHub reads (`git fetch`, `gh`) need network outside the sandbox** — fetch before judging branch or merge state
- **Visualization**: For analysis outputs and publication-quality charts, use Datawrapper (preferred, requires `DATAWRAPPER_API_TOKEN`) or Python data science libraries (seaborn, matplotlib, plotnine, bokeh). Chart.js is acceptable only for quick dev prototyping during iteration — never for analysis outputs or anything shared externally.

## Pipeline

### Phase 1: Dataset Curation (complete)

NIH ExPORTER bulk downloads → keyword filtering → unified dataset.

```
process_all_years.py  →  filter_biomarker_projects.py  →  data/filtered/biomarker_FY*.csv
                                                              ↓
                                                       create_unified_dataset.py
                                                              ↓
                                                       nih_biomarker_unified_2004-2024.csv (344,550 grants)
```

- **Term sets**: core (13 terms) and expanded (36 terms). Core includes explicit biomarker/marker language plus definite biomarker concepts (endophenotype, intermediate outcome/endpoint, digital endpoint) and decision-making terms (risk stratification, patient selection, companion diagnostic, predicting response, response to therapy). Expanded adds diagnostics, stratification, precision medicine, and signature terms.
- **Facility screening**: `is_facility_grant()` excludes infrastructure sub-projects (Administrative Core, Shared Resource, etc.) by title pattern. Center grants themselves are NOT excluded.
- `EXPLICIT_BIOMARKER` column flags core-term matches
- Data quality: FY2005 PROJECT_TERMS 68% populated; FY2006 PROJECT_TERMS empty
- See `README.md` for full script docs and commands

### Phase 2: LLM Classification (current focus)

3-dimension rubric grading using **[Inspect AI](https://inspect.aisi.org.uk/)** (UK AISI's eval framework) — see Issue #7, PR #18.

```
RUBRIC.md ──parse_rubric_codes()──→ code enum sets (22 + 10 + 5)
    │                                       │
    └─→ grader_prompt.py (build_system_prompt)
              │
              ↓
        inspect_task.py
         ├─ record_to_sample()  ← CSV (NCI/pilot/NIEHS samples, gold-labeled calibration); empty abstracts skipped
         ├─ rubric_solver()     ← system prompt from RUBRIC.md
         ├─ generate()          ← LLM call (model and config via CLI)
         └─ rubric_scorer()     ← tolerant JSON parse + code enum check
              │
              ↓
        .eval logs → inspect view / inspect score (re-score) / post-hoc analysis
```

**Key design decisions:**
- Code enums are **parsed from RUBRIC.md at import time** (not hardcoded) — rubric edits auto-propagate
- Step 0 exit codes (`not_applicable`, `disease_non_biomarker`) require null Dim2/Dim3; the scorer exempts them from Dim2/Dim3 validation (`NULL_DIM23_CODES`)
- The scorer tolerates prose around the JSON, trailing commas, and self-corrections (takes the last JSON object). Separator variants of real codes map via `CODE_ALIASES`, and each replacement is recorded in score metadata. Structured output via `response_schema` is planned (Issue #49).
- Generation config is **not hardcoded** — set via CLI. Do not pass `--temperature` to Claude 5.5 models (400 error), and avoid a low `--max-tokens` (thinking tokens count against it)
- Gold-label support: CSVs with `GOLD_DIM1/DIM2/DIM3` columns → `Sample.target` for expert-label scoring
- `inspect eval-set` runs several models in one command with automatic retry/resume; `inspect score` re-scores saved outputs without new API calls

**Provider notes** (Inspect ≥ 0.3.287, `anthropic` SDK in `.venv`):
- Anthropic prompt caching is automatic. The ~9.9K-token system prompt is read from cache on ~90% of calls.
- Claude 5.5 safety classifiers can refuse (`stop_reason == "content_filter"`). Retry those sample IDs with `--sample-id`; use `--fallback-models` only at Manjari's direction, since it changes the judge.
- `.eval` logs are zstd-compressed: read them with `inspect_ai.log.read_eval_log`, not `zipfile`
- Batch mode failed for Gemini and Together in April 2026 (see manifest). For Anthropic it is 50% cheaper but can take up to 24h.

**Run history and which log to analyze:** `logs/manifest.csv` (rows whose `reason` says "USE THIS").

- Abstracts from `~/Downloads/RePORTER_PRJABS_C_FY*.zip` (FY2016 present)

### Grader Sensitivity & Judge Evaluation (Issue #20)

Before scaling to 270K, sensitivity analysis on the oncology sample:
self-consistency, inter-model agreement, known disagreement patterns,
gold-label calibration. See Issue #20 for full plan.

**Ecosystem tools** (for post-hoc analysis on `.eval` logs):
- **[HiBayES](https://github.com/UKGovernmentBEIS/hibayes)** — Hierarchical Bayesian analysis, first-class Inspect integration (same AISI team)
- **[CJE](https://github.com/cimo-labs/cje)** — Calibrates cheap judge scores against oracle slice, valid CIs
- **[RAND JRH](https://github.com/RANDCorporation/judge-reliability-harness)** — Perturbation-based judge stress testing

## Key Files

| File | Role |
|------|------|
| `data/RUBRIC.md` | Source of truth: classification rubric with "Assign when..." definitions |
| `scripts/grader_prompt.py` | Loads RUBRIC.md at runtime and builds the system prompt and user-message template |
| `scripts/utils.py` | Shared utilities: `load_env()`, `parse_llm_json()` (tolerant JSON extraction) |
| `scripts/abstract_loader.py` | Loads abstracts from RePORTER zip files |
| `scripts/generate_review.py` | Expert review HTML generator (anti-anchoring design) |
| `inspect_task.py` | Inspect AI task: dataset loader, solver, scorer. Parses codes from RUBRIC.md, supports gold labels, CLI-controlled config. |
| `scripts/sample_grants.py` | Tiered multi-IC pilot sampler (P30 filter, abstract join) |
| `scripts/sample_ic_by_year.py` | Fixed count per fiscal year for one IC, same P30 filter and abstract join (e.g. NIEHS) |
| `scripts/build_selective_sample.py` | Gold + stratified + prior-disagreement pilot sample (PR #48, not yet on main) |
| `scripts/analyze_eval_results.py` | Reads `.eval` logs for analysis (needs updating for zstd logs) |
| `scripts/legacy/` | Archived pre-Inspect scripts: `run_calibration.py`, `run_batch_grading.py`, `analyze_agreement.py`, `extract_disagreements.py` |
| `scripts/filter_biomarker_projects.py` | Filters NIH ExPORTER CSVs by keyword term sets (core/expanded) with facility screening |
| `scripts/keyword_terms.py` | Biomarker keyword term sets, matching logic, and facility screening (imported by filter and analysis scripts) |
| `scripts/analyze_keyword_distribution.py` | PROJECT_TERMS distribution analysis for keyword coverage audit (issue #27) |
| `scripts/process_all_years.py` | Batch download + filter FY2004-2024 |
| `scripts/create_unified_dataset.py` | Merges filtered year CSVs into single dataset |
| `data/grader_calibration_examples.csv` | Calibration examples; rows with `GOLD_DIM1` (23) are gold-labeled |
| `data/pilot_sample_12IC_tiered_seed42.csv` | 20,644 grants across 12 ICs, tiered rates (5% CA, 7% large, 10% small), seed 42; includes ABSTRACT_TEXT; P30 excluded unless NIH_SPENDING_CATS contains 'clinical' |
| `data/nci_sample_v31_seed42.csv` | 3,770 CA grants (3,718 with abstracts) — CA subset of pilot_sample_12IC, on GitHub release dataset-release-v3.1 |
| `data/selective_v1_nci.csv` | 103-grant pilot: 23 gold + 50 random CA (seed 4242) + 30 April Gemini/GPT-OSS disagreements |
| `data/niehs_sample_byyear_seed42.csv` | 300 NIEHS grants: 10/yr FY2004–2013, 20/yr FY2014–2023, seed 42 |
| `data/niehs300_plus_grant_abstracts_v31.csv` | NIEHS 300 + 20 grants from `~/Downloads/grant_abstracts_v31.csv` (`SOURCE` column; prior labels in `PRIOR_*`) |
| `data/march-pilot-nci-2k/` | Archived March 2026 pilot: oncology sample, grading outputs, calibration results, grading visualizations |
| `data/nih_biomarker_unified_2004-2024.csv` | 344,550 grants (276K keyword + 68K abstract-only), 30 columns, v3.1 |
| `logs/manifest.csv` | Run manifest for all `inspect eval` / `inspect score` calls — append after every run (schema: Issue #41) |

## Commands

```bash
# Phase 1: Data curation
python3 scripts/process_all_years.py --start-year 2004 --end-year 2024 --skip-download --raw-dir ~/Downloads
python3 scripts/create_unified_dataset.py
python3 scripts/generate_summary.py

# Phase 2: Sampling
python3 scripts/sample_grants.py --unified data/nih_biomarker_unified_2004-2024.csv --abs-dir ~/Downloads --seed 42
python3 scripts/sample_ic_by_year.py --ic ES --per-year 2004-2013:10 --per-year 2014-2023:20 --out data/niehs_sample_byyear_seed42.csv

# Phase 2: LLM grading (Inspect AI) — full procedure: .claude/skills/grading-run/SKILL.md
set -a; . ./.env; set +a          # loads ANTHROPIC_API_KEY, GEMINI_API_KEY, ...
INSPECT=.venv/bin/inspect
# Smoke test (3 samples)
$INSPECT eval inspect_task.py --model anthropic/claude-sonnet-5-5 -T dataset_path=data/selective_v1_nci.csv --limit 3 --log-dir logs/YYYY-MM-DD_smoke-test-3_sonnet-5.5/
# Multi-model run (one eval-set, one .eval per model)
$INSPECT eval-set inspect_task.py --model anthropic/claude-opus-5-5,anthropic/claude-sonnet-5-5 -T dataset_path=data/nci_sample_v31_seed42.csv --log-dir logs/YYYY-MM-DD_nci-3718_opus-sonnet-5.5/
# Retry refused samples
$INSPECT eval inspect_task.py --model anthropic/claude-opus-5-5 -T dataset_path=<csv> --sample-id <id1>,<id2> --log-dir logs/YYYY-MM-DD_<sample>-<n>-refused_opus-5.5_retry/
# Re-score saved outputs after a scorer/parser change (no API calls; never overwrite originals)
$INSPECT score <log.eval> --scorer inspect_task.py@rubric_scorer --action overwrite --output-file logs/YYYY-MM-DD_<what>_rescored-<why>/<log.eval name> </dev/null
# Browse results
$INSPECT view
# ALWAYS after any inspect eval/score: append a row to logs/manifest.csv (Issue #41)

# Phase 3: Expert review
python3 scripts/generate_review.py --examples data/grader_calibration_examples.csv --results-dir data/

# Utilities
ruff check . && ruff format .
python3 -m unittest tests.test_inspect_task -v
python3 -m unittest tests.test_filter_biomarker_projects -v
```

## Session Workflow

1. **At session start**: Read `docs/session-notes/` for prior context before taking action. Identify the most recent note and understand where we left off.
2. **Before acting**: Confirm you understand the user's goals for this session.
3. **At session end**: Write a session note to `docs/session-notes/YYYY-MM-DD-<topic>.md` capturing:
   - Goal for the session
   - What was tried (including dead ends)
   - What was done (concrete outcomes)
   - Next session priorities

## Status

See `docs/session-notes/` for current project status. The most recent note captures where we left off.
