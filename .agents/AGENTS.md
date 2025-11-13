# Repository Guidelines

**For Claude Agents:** See `.agents/CLAUDE.md` for comprehensive data structure documentation, implementation decisions, and common tasks.

This repository builds a reproducible pipeline to quantify NIH funding across biomarker research phases while minimizing brittle UI search filters. We will extract a smaller, targeted dataset from SciOP snapshots/code focused on biomarker and biomarker‑adjacent research (instead of querying NIH Reporter directly). The workflow is:
- Ingest SciOP snapshots as the primary source and extract a targeted subset using permissive biomarker/adjacency heuristics to keep datasets small (~50–150 MB per year/cohort).
- Normalize and deduplicate projects; preserve stable identifiers for reproducibility.
- Classify each project into biomarker phases: technology development, clinical discovery, development/analytical validation, and clinical validation (including regulatory and non‑regulatory decision support). Favor transparent LLM graders with a documented rubric and seeded prompts; augment with lightweight heuristics.
- Aggregate spend by phase, institute, mechanism, and year; export analysis tables and small artifacts for review.


## Project Structure & Module Organization
- Root: coordination and docs.
- `scripts/`: operational utilities (e.g., `scripts/nih_bulk_downloader.py` — experimental).
- `nih-reporter-skill/`: NIH Reporter usage docs/examples (`SKILL.md`).
- Proposed layout as the project grows:
  - `src/`: reusable Python packages (`fetch/`, `parse/`, `grade/`, `agg/`).
  - `tests/`: pytest suite mirroring `src/`.
  - `data/` (git-ignored): local cache (CSV/Parquet). Target per-file size ≈ 50–150 MB.

## Build, Test, and Development Commands
- Show downloader help: `python3 scripts/nih_bulk_downloader.py --help`
- Lint: `ruff check .`  |  Format: `ruff format .` or `black .`
- Type check (optional): `pyright`
- Tests: `pytest -q` (e.g., `pytest -k grade --maxfail=1`)
- Example fetch entrypoint (planned): `python3 -m src.fetch.export --year 2022 --out data/raw/2022.csv`

## Coding Style & Naming Conventions
- Python 3.10+: 4-space indent; ~100-char lines; `pathlib`, f-strings.
- Files/modules: snake_case (`biomarker_phase_classifier.py`).
- Functions: verb_noun (`fetch_projects`, `shard_csv`, `grade_phase`).
- Separate concerns: `fetch` (I/O + backoff + caching) → `parse` (normalize) → `grade` (LLM/heuristics) → `agg` (rollups).

## Testing Guidelines
- Use `pytest`; name tests `test_*.py` in `tests/`.
- Mock network and LLM calls; place fixtures under `tests/fixtures/`.
- Cover parsing, sharding (≤150 MB/file), dedupe, and grading rubric.
- Run: `pytest -q` and measure critical-path coverage; add regressions for bugs.

## Data Sourcing Strategy
- Primary source: SciOP NIH Reporter snapshots: https://sciop.net/datasets/nih-reporter
- Build a targeted biomarker-focused subset by streaming CSVs, selecting only needed columns, applying permissive keyword heuristics over title/abstract, and optionally early LLM triage to drop clearly unrelated records. Retain enough context fields for downstream grading.
- Keep raw data out of Git; cache under `data/` with checksums and a README describing provenance and exact extraction commands.

## Data Structure & Multi-Year Funding (CRITICAL)
- **NIH ExPORTER provides one file per fiscal year** (e.g., `RePORTER_PRJ_C_FY2023.csv`).
- **Multi-year projects appear once per FY file** with that year's funding in TOTAL_COST.
- **Key identifiers:**
  - `APPLICATION_ID`: Unique per fiscal year award (changes annually: `10001234`, `10001234-A1`, `10001234-A2`)
  - `CORE_PROJECT_NUM`: Stable across all years (e.g., `R01AG123456`)
  - `FY`: Fiscal year (2006-2024)
  - `TOTAL_COST`: Annual funding for that specific FY (NOT cumulative)
- **Deduplication requirement:** Use `(APPLICATION_ID, FY)` as unique key to preserve all yearly funding records. Never deduplicate by APPLICATION_ID alone or CORE_PROJECT_NUM alone when processing multi-year data.
- **Total project funding:** Aggregate by `SUM(TOTAL_COST) GROUP BY CORE_PROJECT_NUM` after filtering.
- **Rationale:** We need the most granular funding level to accurately calculate total research spending across biomarker phases and years.
- **See `.agents/CLAUDE.md` for detailed data model documentation and implementation examples.**

## Commit & Pull Request Guidelines
- Commits: imperative, scoped prefix, e.g., `fetch: add sciop sharder`, `grade: calibrate rubric`.
- PRs must include: purpose, dataset scope (years/institutes), repro commands, and sample outputs; note caching/ID stability.

## Security & Configuration Tips
- Never commit credentials or PII. Use env vars and a git-ignored `.env`.
- Respect NIH rate limits; implement exponential backoff and request IDs.
- Version LLM prompts; log seeds and templates for reproducibility.
