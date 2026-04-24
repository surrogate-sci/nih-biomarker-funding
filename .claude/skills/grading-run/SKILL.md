---
name: grading-run
description: Launch an inspect eval grading run and append the result to logs/manifest.csv. Use when starting any LLM grading run — calibration, pilot, sensitivity, or rubric variant.
---

# Grading Run

Collect the following inputs before doing anything. The invoking agent should
have this context from the current session; confirm before proceeding.

| Input | Notes |
|-------|-------|
| `model` | One model string, or comma-separated for eval-set |
| `dataset` | Path to the grant sample CSV in `data/` |
| `rubric` | Path to rubric file (default: `data/RUBRIC.md`; override for A/B variants) |
| `temperature` | Numeric |
| `limit` | Optional; omit for full sample |
| `epochs` | Optional; for self-consistency runs |
| `reason` | Free text — purpose, experiment type, any caveats; include condition label for variant runs |

## Steps

1. **Compute rubric version:**
   ```bash
   git log --format=%h -1 <rubric-path>
   ```

2. **Build the inspect command:**
   ```bash
   # Single model
   inspect eval inspect_task.py \
     --model <model> --temperature <temp> \
     [--limit <n>] [--epochs <n>] \
     --log-dir logs/<slug>/

   # Multi-model
   inspect eval-set inspect_task.py \
     --model <model-a>,<model-b> \
     --log-dir logs/<slug>/
   ```
   The log-dir slug should identify the run (sample, model, any variant label).

3. **Run it** and stream output so the user can monitor progress.

4. **Extract from the resulting `.eval` filename:**
   - `run_id`, `log_path`, `timestamp`

5. **Append one row to `logs/manifest.csv`:**

   | Field | Value |
   |-------|-------|
   | `run_id` | from `.eval` filename |
   | `timestamp` | from `.eval` filename |
   | `log_path` | relative path to `.eval` |
   | `status` | `complete` or `failed` |
   | `reason` | user-provided |
   | `model` | as specified |
   | `rubric_version` | git hash from step 1 |
   | `dataset` | filename as specified |
   | `n_samples` | actual count graded |
   | `temperature` | as specified |

   Always write the row — even for failed or partial runs.

6. **Print summary:** model, n_samples, log_path, manifest row written.

## Invariants

- `logs/manifest.csv` must already exist. If missing, stop and ask — do not create it.
- Never overwrite or delete existing manifest rows.
- `reason` is the human-readable record. Write it to be useful months from now.
