# NIH Biomarker Funding Analysis

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

## Rules

- **RUBRIC.md is scientific content** — do not modify definitions without Manjari's explicit direction
- **"I draft, you correct" workflow** — Manjari dictates scientific substance; Claude organizes/formats
- **Manjari edits concurrently in Cursor** — check for file modifications before overwriting; preserve her changes
- **Refactoring/cleanup → PR** (not direct commit to main). Doc updates → direct commit is fine.
- **`data/` is gitignored** — use `git add -f` for tracked files (RUBRIC.md, calibration CSVs, results)
- **Commit style**: imperative, scoped prefix: `grade: calibrate rubric`, `fetch: add sharder`
- **Don't use**: `_archive/`, `../edison-benchmarks/`, old skill dirs
- **Don't invent scientific positions** — never paraphrase domain claims or add causal language Manjari didn't provide
- **After every `inspect eval` run** — append a row to `logs/manifest.csv` before moving on (schema: Issue #41)
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

3-dimension rubric grading via LLM ensemble using **[Inspect AI](https://inspect.aisi.org.uk/)** (UK AISI's eval framework) — see Issue #7, PR #18.

```
RUBRIC.md ──parse_rubric_codes()──→ code enum sets (17 + 10 + 5)
    │                                       │
    └─→ grader_prompt.py (build_system_prompt)
              │
              ↓
        inspect_task.py
         ├─ record_to_sample()  ← CSV (oncology/calibration/gold-labeled)
         ├─ rubric_solver()     ← system prompt from RUBRIC.md
         ├─ generate()          ← LLM call (model/temp/max_tokens via CLI)
         └─ rubric_scorer()     ← JSON validation + code enum check
              │
              ↓
        .eval logs → inspect view / HiBayES / post-hoc analysis
```

**Key design decisions:**
- Code enums are **parsed from RUBRIC.md at import time** (not hardcoded) — rubric edits auto-propagate
- `temperature` and `max_tokens` are **not hardcoded** — set via CLI (`--temperature 0.0`, `--max-tokens 500`)
- Gold-label support: CSVs with `GOLD_DIM1/DIM2/DIM3` columns → `Sample.target` for expert-label scoring
- Same task works at all scales: `--limit 25` for calibration, `--batch` for 270K production run

**Legacy scripts** (still present, being replaced by `inspect_task.py`):
`run_calibration.py`, `run_batch_grading.py`, `analyze_agreement.py`, `extract_disagreements.py`

Inspect provides: batch API support (OpenAI, Anthropic, Google — 50% cost savings),
`eval-set` for multi-model runs with automatic retry/resume, caching,
`.eval` structured logging with `inspect view`, deferred scoring (`--no-score` +
`inspect score`) for re-scoring without regenerating outputs.

- **Models**: Gemini 2.5 Flash Lite + GPT-4.1-mini (primary), Sonnet 4.6 Batch API (tiebreaker on ~28% disagreements). ~$350-480 with batch API for 270K grants.
- **Rubric**: 17 Dim1 (biomarker use) + 10 Dim2 (research design) + 5 Dim3 (evidence strength) codes — parsed from `data/RUBRIC.md`
- Abstracts from `~/Downloads/RePORTER_PRJABS_C_FY*.zip` (FY2016 missing)

### Grader Sensitivity & Judge Evaluation (Issue #20)

Before scaling to 270K, sensitivity analysis on the 3K oncology sample:
temperature self-consistency, inter-model agreement, known disagreement patterns,
gold-label calibration. See Issue #20 for full plan.

**Ecosystem tools** (for post-hoc analysis on `.eval` logs):
- **[HiBayES](https://github.com/UKGovernmentBEIS/hibayes)** — Hierarchical Bayesian analysis, first-class Inspect integration (same AISI team)
- **[CJE](https://github.com/cimo-labs/cje)** — Calibrates cheap judge scores against oracle slice, valid CIs
- **[RAND JRH](https://github.com/RANDCorporation/judge-reliability-harness)** — Perturbation-based judge stress testing

## Key Files

| File | Role |
|------|------|
| `data/RUBRIC.md` | Source of truth: classification rubric with "Assign when..." definitions |
| `scripts/grader_prompt.py` | Loads RUBRIC.md at runtime, constructs system prompt, calls OpenRouter/OpenAI |
| `scripts/utils.py` | Shared utilities: `load_env()`, `parse_llm_json()` |
| `scripts/abstract_loader.py` | Loads abstracts from RePORTER zip files |
| `scripts/generate_review.py` | Expert review HTML generator (anti-anchoring design) |
| `inspect_task.py` | Inspect AI task: Dataset loader, Solver, Scorer. Parses codes from RUBRIC.md, supports gold labels, CLI-controlled config. |
| `scripts/legacy/run_calibration.py` | (archived) Legacy calibration runner — superseded by Inspect task |
| `scripts/legacy/run_batch_grading.py` | (archived) Legacy batch grader — superseded by Inspect eval/eval-set |
| `scripts/legacy/analyze_agreement.py` | (archived) Inter-model agreement analysis |
| `scripts/legacy/extract_disagreements.py` | (archived) Disagreement pattern extractor |
| `scripts/filter_biomarker_projects.py` | Filters NIH ExPORTER CSVs by keyword term sets (core/expanded) with facility screening |
| `scripts/keyword_terms.py` | Biomarker keyword term sets, matching logic, and facility screening (imported by filter and analysis scripts) |
| `scripts/analyze_keyword_distribution.py` | PROJECT_TERMS distribution analysis for keyword coverage audit (issue #27) |
| `scripts/process_all_years.py` | Batch download + filter FY2004-2024 |
| `scripts/create_unified_dataset.py` | Merges filtered year CSVs into single dataset |
| `data/grader_calibration_examples.csv` | 25 easy cases (explicit biomarker terms from 2012 & 2022) |
| `data/pilot_sample_12IC_tiered_seed42.csv` | 21,424 grants across 12 ICs, tiered rates (5% CA, 7% large, 10% small), seed 42; includes ABSTRACT_TEXT |
| `data/march-pilot-nci-2k/` | Archived March 2026 pilot: oncology sample, grading outputs, calibration results, grading visualizations |
| `data/nih_biomarker_unified_2004-2024.csv` | 344,550 grants (276K keyword + 68K abstract-only), 30 columns, v3.1 |
| `logs/manifest.csv` | Run manifest for all `inspect eval` calls — append after every run (schema: Issue #41) |

## Commands

```bash
# Phase 1: Data curation
python3 scripts/process_all_years.py --start-year 2004 --end-year 2024 --skip-download --raw-dir ~/Downloads
python3 scripts/create_unified_dataset.py
python3 scripts/generate_summary.py

# Phase 2: Sampling
python3 scripts/sample_grants.py --unified data/nih_biomarker_unified_2004-2024.csv --abs-dir ~/Downloads --seed 42

# Phase 2: LLM grading (Inspect AI)
# Source GEMINI_API_KEY before running: export $(grep -v '^#' .env | xargs)
INSPECT=/Users/mnarayan/Documents/Coding/Cloud/nih-biomarker-funding/.venv/bin/inspect
# Pipeline smoke test (5 samples)
$INSPECT eval inspect_task.py --model google/gemini-2.5-flash-lite --temperature 0.0 --limit 5 --log-dir logs/test-pipeline/
# NCI slice (~4.2K grants, batch API)
$INSPECT eval inspect_task.py --model google/gemini-2.5-flash-lite -T dataset_path=data/nci_sample_v31_seed42.csv --temperature 0.0 --batch --log-dir logs/nci-v31-gemini-flash-lite/
# Multi-model comparison via eval-set
$INSPECT eval-set inspect_task.py --model openai/gpt-4.1-mini,google/gemini-2.5-flash-lite --log-dir logs/
# Sensitivity: self-consistency (Issue #20)
$INSPECT eval inspect_task.py --model google/gemini-2.5-flash-lite --temperature 0.1 --epochs 3 --limit 100
# Browse results
$INSPECT view
# ALWAYS after any inspect eval: append a row to logs/manifest.csv (Issue #41)

# Phase 3: Analysis + Expert review
python3 scripts/analyze_agreement.py --data-dir data/
python3 scripts/extract_disagreements.py --data-dir data/
python3 scripts/generate_review.py --examples data/grader_calibration_examples.csv --results-dir data/

# Utilities
ruff check . && ruff format .
python3 -m unittest tests.test_generate_review -v
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
