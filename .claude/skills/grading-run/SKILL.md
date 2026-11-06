---
name: grading-run
description: Launch an Inspect grading run (or re-score / refusal retry) and append the result to logs/manifest.csv. Use when starting any LLM grading run — smoke test, calibration, pilot, production, sensitivity, rubric variant — or when re-scoring saved .eval logs after a scorer change.
---

# Grading Run

Any agent can follow this file, not only Claude Code. Collect the following inputs
before doing anything. The invoking agent should have this context from the current
session; confirm before proceeding, and confirm the expected cost before any run that
spends more than a few dollars.

| Input | Notes |
|-------|-------|
| `model` | One model string, or comma-separated for `eval-set` (e.g. `anthropic/claude-opus-5-5,anthropic/claude-sonnet-5-5`) |
| `dataset` | Path to the grant sample CSV in `data/` |
| `rubric` | Path to rubric file (default: `data/RUBRIC.md`; override for A/B variants) |
| `temperature` | Optional. **Omit for Claude 5.5 models** (they reject it with a 400). Record `default` in the manifest when omitted. |
| `limit` / `sample_id` | Optional; `--limit` for smoke tests, `--sample-id` for refusal retries |
| `epochs` | Optional; for self-consistency runs |
| `reason` | Free text — purpose, experiment type, any caveats; include condition label for variant runs |

## Steps

1. **Compute rubric version.** Commit rubric and scorer changes first, so the hash means something:
   ```bash
   git log --format=%h -1 <rubric-path>
   ```

2. **Name the log folder for humans:** `logs/YYYY-MM-DD_<sample>-<n>_<models>[_<purpose>]/`
   (e.g. `logs/2026-11-06_nci-3718_opus-sonnet-5.5/`, `logs/2026-11-06_nci-6-refused_opus-5.5_retry/`).
   No commit hashes in folder names; they go in the manifest.

3. **Load keys and build the command** (Inspect does not read `.env` on its own here):
   ```bash
   set -a; . ./.env; set +a
   # Single model
   .venv/bin/inspect eval inspect_task.py --model <model> \
     -T dataset_path=<csv> [--limit <n>] [--epochs <n>] [--temperature <t>  # non-Claude only] \
     --log-dir logs/<folder>/
   # Several models: one eval-set, one .eval per model, automatic retry/resume
   .venv/bin/inspect eval-set inspect_task.py --model <model-a>,<model-b> \
     -T dataset_path=<csv> --log-dir logs/<folder>/
   ```
   Do not pass a low `--max-tokens`: thinking tokens count against it. Anthropic prompt caching is automatic.

4. **Run it** and stream output so the user can monitor progress. Runs are fast and parallel (~10 connections per model), so spend arrives within minutes.

5. **Check the results** with `inspect_ai.log.read_eval_log`. Logs are zstd-compressed, so `zipfile` won't open them.
   - `valid_json` / `valid_codes` counts, and what the invalid ones are
   - **Refusals:** samples with `output.stop_reason == "content_filter"`. Retry them once with `--sample-id <ids>` into a `_retry` folder. Only use `--fallback-models` if the user asks (it changes the judge for those rows). Record any that stay refused.

6. **Re-score after a scorer or parser change** (no API calls). Never overwrite the original log:
   ```bash
   .venv/bin/inspect score <original.eval> --scorer inspect_task.py@rubric_scorer \
     --action overwrite --output-file logs/<YYYY-MM-DD_what_rescored-why>/<original.eval name>
   ```
   `--scorer` is required; without it Inspect cannot load the scorer from the recorded task file.

7. **Extract from each resulting `.eval` filename:** `run_id`, `log_path`, `timestamp`.

8. **Append one row per `.eval` to `logs/manifest.csv`** (runs, retries, and re-scores):

   | Field | Value |
   |-------|-------|
   | `run_id` | from `.eval` filename |
   | `timestamp` | from `.eval` filename |
   | `log_path` | relative path to `.eval` |
   | `status` | `complete`, `partial`, or `failed` |
   | `reason` | user-provided; for retries/re-scores, name the run they supersede and why |
   | `model` | as specified |
   | `rubric_version` | git hash from step 1 |
   | `dataset` | filename as specified |
   | `n_samples` | actual count graded |
   | `temperature` | as specified, or `default` |

   Always write the row — even for failed or partial runs.

9. **Print summary:** model, n_samples, validity, refusals, cost if known, log_path, manifest row written.

## Invariants

- `logs/manifest.csv` must already exist. If missing, stop and ask — do not create it.
- Never overwrite or delete existing manifest rows. If a log folder is renamed, only its `log_path` may be updated.
- Never overwrite or delete a paid `.eval` log; re-scores go to a new folder.
- `reason` is the human-readable record. Write it to be useful months from now.
- `logs/` is gitignored: commit the manifest with `git add -f logs/manifest.csv`.
