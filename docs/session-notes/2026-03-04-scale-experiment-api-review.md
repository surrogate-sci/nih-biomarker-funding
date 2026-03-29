# Session Notes: 2026-03-04 — Scale Experiment & API Review

## What was done

1. **Built 4 new scripts** for mid-scale experiment (2,000 NCI oncology grants):
   - `scripts/abstract_loader.py` — shared utility for loading abstracts from RePORTER zips
   - `scripts/sample_oncology.py` — stratified NCI sample (100/year × 20 years) + abstract join
   - `scripts/run_batch_grading.py` — serial batch grading with JSONL checkpoint/resume
   - `scripts/generate_review.py` — standalone HTML for expert rubric review (anti-anchoring)

2. **Ran the sampling pipeline** — 2,000 grants sampled, 1,952 with abstracts, FY2016 skipped

3. **Ran grading experiments** and discovered significant API performance issues:
   - Gemini 2.5 Flash Lite via OpenRouter: 4.2s/call, 0.2% error rate — acceptable
   - GPT-4o-mini via OpenRouter: 24.4s/call, 8% 502 error rate — unacceptable
   - GPT-4.1-mini via OpenRouter: started but not completed

4. **Code review** identified critical issues in the API calling infrastructure

## Key Insights

### OpenRouter performance is model-dependent
- Gemini routes fine; OpenAI models route poorly (high latency, 502 errors)
- OpenRouter's value is multi-model routing — if calling one model at a time, direct API is better
- For production: use provider APIs directly or batch endpoints

### Serial API calls don't scale
- 1,952 grants at ~5s/call = ~2.7 hours per model (serial)
- 270K grants at ~5s/call = ~13 days per model (serial)
- **For production, use batch APIs**: OpenAI Batch API (50% cheaper, handles parallelism), Google Vertex Batch
- Async concurrency with `aiohttp` is the middle ground for OpenRouter

### Model selection update
- **GPT-4.1-mini replaces GPT-4o-mini** — better instruction-following (49% vs 29% on OpenAI evals), $0.40/$1.60 per M tokens (vs $0.15/$0.60)
- Gemini 2.5 Flash Lite remains cheapest ($0.075/$0.30 per M tokens)
- Full run cost estimate: ~$700-900 total across both models + tiebreaker

### Code review findings (prioritized)
1. **Critical**: Error records in JSONL checkpoint are treated as "done" — transient 502s permanently lose grants. Fix: separate succeeded/errored sets, add `--retry-errors` flag.
2. **Critical**: No timeout on `urllib.request.urlopen()` — hung connections block forever. Fix: add `timeout=60`.
3. **Important**: No retry logic — need exponential backoff (2 retries → 8% error rate becomes 0.05%).
4. **Important**: `grader_prompt.py` is a mixed-concern file (prompts + API clients + legacy code + tests). Extract `api_client.py` before production.
5. **Important**: `.env` loading duplicated across 3 files. Consolidate.
6. **Suggestion**: Legacy system prompt in `grader_prompt.py` uses outdated code names (e.g., `methods_statistical`, `predictive_nonspecific`). Delete or quarantine.

### Worktree gotchas
- `.env` file is in the main repo, not in the worktree (gitignored). Had to symlink.
- `data/nih_biomarker_unified_2004-2024.csv` is gitignored — not available in worktree. Must pass explicit `--unified` path pointing to main repo.
- Calibration results JSONs are tracked via `git add -f` so they DO appear in worktree.

## Decisions made
- Strict NCI filter (`ADMINISTERING_IC == 'CA'`) for oncology, not broader cancer keyword search
- Expert review: primary + secondary codes for Dim1/Dim2, primary only for Dim3 (6 dropdowns total)
- Standalone HTML for expert review (not spreadsheet or Jupyter)
- Shared abstract loader module (not pre-consolidated CSV)
- GPT-4.1-mini replaces GPT-4o-mini going forward

## Next steps
1. Fix critical code review issues (#1-3) before any production run
2. Build `run_batch_api.py` using OpenAI Batch API + Google Batch for production 270K run
3. Manjari: review 25 calibration examples via `data/expert_review.html`
4. Cleanup PR (Task 3 from existing plan) — still pending
