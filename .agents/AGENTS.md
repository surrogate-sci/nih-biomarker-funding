# Repository Guidelines

## Project Goal

Produce data for a policy-level blog post testing the hypothesis that most NIH biomarker
funding operates without a clear estimand (causal or decision-theoretic), and that
surrogacy/mechanistic validation is an afterthought. The pipeline keyword-filters 20 years
of NIH ExPORTER data into ~270K biomarker grants, then LLM-grades each on 3 dimensions
using a custom rubric extending FDA-NIH BEST.

## Critical Rules

- **`data/RUBRIC.md` is the classification source of truth** — do not modify definitions without Manjari's explicit direction. This is a scientific document.
- **`data/` is gitignored** — use `git add -f` for files that need tracking (RUBRIC.md, calibration CSVs, results).
- **Don't use**: `_archive/`, `../edison-benchmarks/` (outdated prior analysis with ~50% ambiguous classifications).

## Project Structure

- `scripts/`: all pipeline scripts (filtering, grading, calibration, analysis)
- `data/`: gitignored dataset cache; tracked exceptions: `RUBRIC.md`, `filtered/SUMMARY.md`, calibration files
- `data/RUBRIC.md`: 17 Dim1 (biomarker use) + 10 Dim2 (research design) + 5 Dim3 (evidence strength) codes
- `docs/plans/`: design documents and implementation plans
- `_archive/`: old skill directories (do not use)

## Build, Test, and Development Commands

```bash
# Phase 1: Data curation (already complete, run only if re-filtering)
python3 scripts/process_all_years.py --start-year 2004 --end-year 2024 --skip-download --raw-dir ~/Downloads
python3 scripts/create_unified_dataset.py
python3 scripts/generate_summary.py

# Phase 2: LLM grading
python3 scripts/run_calibration.py --model google/gemini-2.5-flash-lite --limit 5
python3 scripts/run_calibration.py --model openai/gpt-4o-mini

# Lint and format
ruff check .
ruff format .

# Tests (when they exist)
pytest -q
```

## Coding Style & Naming Conventions

- Python 3.10+: 4-space indent; ~100-char lines; `pathlib`, f-strings.
- Files/modules: snake_case (`filter_biomarker_projects.py`).
- Functions: verb_noun (`fetch_projects`, `load_rubric`, `grade_phase`).

## Data Sourcing

- Primary source: NIH ExPORTER bulk CSV downloads (FY2004-2024)
- Keyword filtering via `filter_biomarker_projects.py` with core (4 terms) and expanded (10 terms) term sets
- Abstracts from `~/Downloads/RePORTER_PRJABS_C_FY*.zip` (FY2016 missing)
- Keep raw data out of Git; cache under `data/`

## Commit & Pull Request Guidelines

- Commits: imperative, scoped prefix, e.g., `grade: calibrate rubric`, `fetch: filter FY2024`.
- PRs must include: purpose, repro commands, and sample outputs.

## Security & Configuration

- Never commit credentials or PII. API keys in git-ignored `.env`.
- Version LLM prompts; log model IDs for reproducibility.
