# Session: Regenerate Pilot & Grade NCI Slice — 2026-04-06

## What we did
Reviewed open issues/PRs, identified which LLM grading work is independent, then designed and planned the pilot regeneration + NCI grading pipeline.

## Key decisions
1. **Grade NCI slice only, Gemini Flash Lite only** — cheapest model first (~$10-20 batch). Second model (GPT-4.1-mini, 4.1-nano, or credits) deferred. — Manjari
2. **5% per year, min 50 per IC per year** — gives ~4,210 NCI grants, 21 years including FY2016. — Manjari
3. **Archive March pilot to `data/march-pilot-nci-2k/`** — sample CSV, all grading JSONL, calibration JSON, grading PNGs from visualizations/. Same pattern as `data/oct-2024/`. — Manjari
4. **Legacy scripts to `scripts/legacy/`** — run_batch_grading, run_calibration, analyze_agreement, extract_disagreements. Superseded by Inspect AI. — Manjari
5. **Use existing pilot sampler** — `sample_grants.py` (already on origin/main via PR #22), just change min floor 25→50. No new sampler needed. — joint
6. **Don't regenerate from raw data** — sample from v3.1 unified dataset, join abstracts from RePORTER zips at sample time. Filtered per-year files are the correct universe. — Manjari correction
7. **Stale pilot sample can be deleted** — `pilot_sample_12IC_tiered_seed42.csv` is free to regenerate, never graded. But old grading results are never deleted (cost money). — Manjari

## Corrections received
- Abstracts not in filtered CSVs or unified dataset → still need RePORTER zip join at sample time
- Local `main` was stale — `sample_grants.py` and `inspect_task.py` already on `origin/main` (merged via PRs #18, #22, #26). Must fetch before planning.
- "Don't delete things I spent money on" → grading JSONL files are never deleted, only archived
- Oncology sample also goes in archive (not kept in place) — everything from March pilot stays together
- Old grader scripts are legacy, not for new work — archive to `scripts/legacy/`

## Open questions
- Are FY2016 abstract zips available on disk? (sampler will attempt to load them)
- Issue #40 raised: create unified dataset with abstracts joined (eliminates zip dependency long-term)

## Next steps
- Parallel session executing plan: `docs/plans/2026-04-06-regenerate-pilot-and-grade-nci.md` (7 tasks, already started in separate session)
- After grading completes: build analysis infrastructure for `.eval` logs

## Files created/updated
- `docs/plans/2026-04-06-regenerate-pilot-and-grade-nci-design.md` — design doc
- `docs/plans/2026-04-06-regenerate-pilot-and-grade-nci.md` — implementation plan (7 tasks)
- `memory/feedback-use-filtered-files.md` — sample from filtered files, not raw
- `memory/feedback-never-delete-paid-data.md` — never delete grading results
- Issue #40 created — unified dataset with abstracts
