# Codebase Cleanup & API Architecture Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Clean up dead code, consolidate duplicated patterns, fix critical API issues, and document design decisions — producing a PR that makes the codebase production-ready for the 270K-grant run.

**Architecture:** Extract shared utilities (env loading, JSON parsing, retry logic) from duplicated inline code. Restructure `grader_prompt.py` from a mixed-concern grab-bag into a focused prompt library + separate API client. Remove 4 dead scripts and ~400 lines of legacy code.

**Tech Stack:** Python 3.10+, urllib (existing), no new dependencies

> **Note (2026-03-29):** The API issues (timeout, retry, checkpoint bugs) in Tasks 1-2 are largely
> moot once we migrate to Inspect AI (Issue #7), which handles all of these natively. The cleanup
> in Tasks 3-6 (dead code removal, doc updates, script staging) remains valuable regardless.
> `grader_prompt.py` is kept as a library — the Inspect Solver wraps its `load_rubric()`,
> `build_system_prompt()`, and `create_grading_prompt()` functions.

**Supersedes:** Task 3 from `docs/plans/2026-03-02-calibration-cleanup-scale.md` (which planned a subset of this work).

---

### Task 1: Extract shared utilities into `scripts/utils.py`

Three patterns are copy-pasted across multiple files. Extract once.

**Files:**
- Create: `scripts/utils.py`
- Modify: `scripts/run_calibration.py`
- Modify: `scripts/run_batch_grading.py`

**Step 1: Create `scripts/utils.py`**

```python
"""Shared utilities for NIH biomarker grading scripts."""

import json
import os
from pathlib import Path


def load_env():
    """Load .env file from repo root into os.environ."""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip().strip("\"'")


def parse_llm_json(content: str) -> dict:
    """Strip markdown code fences and parse JSON from LLM response.

    Handles ```json ... ```, bare ``` ... ```, and plain JSON.
    Raises json.JSONDecodeError on malformed JSON.
    """
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    return json.loads(content.strip())
```

**Step 2: Update `run_calibration.py`**

Replace inline `.env` loading (lines 30-37) with `from scripts.utils import load_env`.
Replace inline JSON fence stripping (lines 73-76) with `from scripts.utils import parse_llm_json`.

**Step 3: Update `run_batch_grading.py`**

Replace `load_env()` definition (lines 34-43) with import from `scripts.utils`.
Replace JSON fence stripping in `grade_one()` (lines 91-94) with `parse_llm_json`.

**Step 4: Verify**

Run: `python3 scripts/run_calibration.py --model google/gemini-2.5-flash-lite --limit 1`
Expected: Successfully grades 1 example (confirms imports work).

**Step 5: Commit**

```bash
git add scripts/utils.py scripts/run_calibration.py scripts/run_batch_grading.py
git commit -m "refactor: extract shared utils (load_env, parse_llm_json)"
```

---

### Task 2: Fix critical API issues in `grader_prompt.py`

Three issues discovered during the 2026-03-04 scale experiment:
1. No timeout on `urllib.request.urlopen()` — hung connections block forever
2. No retry logic — transient 502 errors permanently lose grants
3. Checkpoint treats errors as "done" — never retried

**Files:**
- Modify: `scripts/grader_prompt.py` (add timeout to `call_openrouter` and `call_openai`)
- Modify: `scripts/utils.py` (add `call_with_retry`)
- Modify: `scripts/run_batch_grading.py` (fix checkpoint, use retry, add `--retry-errors`)

**Step 1: Add timeout to API calls in `grader_prompt.py`**

In both `call_openrouter()` and `call_openai()`, change:
```python
with urllib.request.urlopen(req) as response:
```
to:
```python
with urllib.request.urlopen(req, timeout=60) as response:
```

**Step 2: Add retry wrapper to `scripts/utils.py`**

```python
import time

def call_with_retry(fn, *args, max_retries=2, base_delay=2.0, **kwargs):
    """Call fn with exponential backoff on failure.

    2 retries with 2s/4s backoff reduces 8% error rate to ~0.05%.
    """
    for attempt in range(max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries:
                raise
            wait = base_delay * (2 ** attempt)
            print(f"  Retry {attempt + 1}/{max_retries} after {wait:.0f}s: {e}")
            time.sleep(wait)
```

**Step 3: Fix checkpoint in `run_batch_grading.py`**

Replace `load_checkpoint()` to distinguish successes from errors:

```python
def load_checkpoint(output_path: Path) -> tuple[set[str], set[str]]:
    """Read existing JSONL. Returns (succeeded_ids, errored_ids)."""
    succeeded: set[str] = set()
    errored: set[str] = set()
    if not output_path.exists():
        return succeeded, errored
    with open(output_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                app_id = record.get("application_id", "")
                if not app_id:
                    continue
                if "error" in record:
                    errored.add(app_id)
                else:
                    succeeded.add(app_id)
            except json.JSONDecodeError:
                continue
    return succeeded, errored
```

Update `run_batch()` to use the new checkpoint and add `--retry-errors` flag.
Update `grade_one()` to use `call_with_retry`.
Change default `--delay` from `1.0` to `0.1`.

**Step 4: Verify**

Run: `python3 scripts/run_batch_grading.py --sample data/oncology_sample_100per_year.csv --model google/gemini-2.5-flash-lite --output /tmp/test_retry.jsonl --limit 3`
Expected: Completes 3 grants. Check that retry logic is wired (may not trigger if no errors).

**Step 5: Commit**

```bash
git add scripts/grader_prompt.py scripts/utils.py scripts/run_batch_grading.py
git commit -m "fix: add API timeout, retry logic, and checkpoint error handling

- 60s timeout on urllib calls (prevents infinite hangs)
- Exponential backoff retry (2 retries, 2s/4s delay)
- Checkpoint distinguishes succeeded vs errored IDs
- Add --retry-errors flag to re-process transient failures
- Reduce default --delay from 1.0 to 0.1"
```

---

### Task 3: Slim `grader_prompt.py` — remove dead code

Remove ~400 lines of dead code. Keep only the active library surface.

**Files:**
- Modify: `scripts/grader_prompt.py`

**Remove:**
- `OUTPUT_SCHEMA` (lines 11-74) — not imported by anything
- `_LEGACY_SYSTEM_PROMPT` (lines 164-270) — uses outdated codes (`prognostic`, `risk`, `predictive_nonspecific`, `methods_statistical`), dangerous if accidentally used
- `test_grader()` (lines 295-396) — dead, never imported
- `run_comparison()` (lines 454-530) — dead, never imported
- `if __name__ == "__main__":` block (lines 533-568) — calls dead functions

**Keep:**
- `load_rubric()`, `build_system_prompt()`, `_SYSTEM_PROMPT_PREAMBLE`, `_SYSTEM_PROMPT_OUTPUT_FORMAT`
- `USER_PROMPT_TEMPLATE`, `create_grading_prompt()`
- `call_openrouter()`, `call_openai()`

**Add:** `_strip_rubric_for_prompt()` — strips `> SOURCE OF TRUTH` preamble and `## References` section before API injection (~100 token savings per call).

**Step 1: Remove dead code**

Delete the sections listed above. Result should be ~150 lines.

**Step 2: Add rubric stripping**

```python
def _strip_rubric_for_prompt(rubric_text: str) -> str:
    """Remove documentation-only sections from rubric before prompt injection."""
    lines = rubric_text.split("\n")
    filtered = []
    skip = False
    for line in lines:
        if line.startswith("> **SOURCE OF TRUTH**"):
            continue
        if line.startswith("## References"):
            skip = True
            continue
        if skip and line.startswith("## "):
            skip = False
        if not skip:
            filtered.append(line)
    return "\n".join(filtered)
```

Wire into `build_system_prompt()`:
```python
def build_system_prompt(rubric_text: str) -> str:
    stripped = _strip_rubric_for_prompt(rubric_text)
    return f"{_SYSTEM_PROMPT_PREAMBLE}\n\n{stripped}\n{_SYSTEM_PROMPT_OUTPUT_FORMAT}"
```

**Step 3: Verify**

Run: `python3 -c "from scripts.grader_prompt import create_grading_prompt; print(len(create_grading_prompt('test', 'test')[0]['content']))"`
Expected: Prints system prompt length (should be ~100 chars shorter than before).

Run: `python3 scripts/run_calibration.py --model google/gemini-2.5-flash-lite --limit 1`
Expected: Successfully grades 1 example.

**Step 4: Commit**

```bash
git add scripts/grader_prompt.py
git commit -m "cleanup: remove ~400 lines of dead code from grader_prompt.py

- Remove OUTPUT_SCHEMA (unused), legacy prompt (outdated codes),
  test_grader(), run_comparison(), __main__ block
- Add _strip_rubric_for_prompt() to trim docs-only sections
- File: 569 → ~150 lines"
```

---

### Task 4: Remove dead scripts and legacy data

**Files:**
- Remove: `scripts/dedupe_and_union.py` — Oct-2024 only, hardcoded personal path
- Remove: `scripts/extract_examples.py` — predates calibration, broken paths
- Remove: `scripts/analyze_keywords.py` — hardcoded to `data/oct-2024/` (broken)
- Remove: `scripts/create_html_charts.py` — reads from `data/oct-2024/` (being removed)
- Remove: `data/oct-2024/` — 6 tracked legacy files

**Step 1: Check what's tracked**

```bash
git ls-files scripts/dedupe_and_union.py scripts/extract_examples.py scripts/analyze_keywords.py scripts/create_html_charts.py data/oct-2024/
```

**Step 2: Remove tracked files**

```bash
git rm scripts/dedupe_and_union.py
git rm scripts/extract_examples.py
git rm scripts/analyze_keywords.py
git rm scripts/create_html_charts.py
git rm -r data/oct-2024/
```

(Some may not be tracked — use `rm` for untracked files, `git rm` for tracked ones.)

**Step 3: Verify no broken imports**

```bash
python3 -c "from scripts.grader_prompt import create_grading_prompt, call_openrouter, call_openai"
python3 -c "from scripts.abstract_loader import load_abstracts_for_year"
python3 -c "from scripts.utils import load_env, parse_llm_json"
```
Expected: All succeed.

**Step 4: Commit**

```bash
git commit -m "cleanup: remove 4 dead scripts and legacy oct-2024 data

- dedupe_and_union.py (Oct-2024 only, hardcoded paths)
- extract_examples.py (predates calibration workflow)
- analyze_keywords.py (hardcoded to removed oct-2024 data)
- create_html_charts.py (reads from removed oct-2024 data)
- data/oct-2024/ (6 legacy analysis files, superseded by unified dataset)"
```

---

### Task 5: Stage new scripts from this session

Add the 4 scripts built during the 2026-03-04 session + session notes.

**Files:**
- Track: `scripts/abstract_loader.py`
- Track: `scripts/sample_oncology.py`
- Track: `scripts/run_batch_grading.py`
- Track: `scripts/generate_review.py`
- Track: `docs/session-notes/2026-03-04-scale-experiment-api-review.md`

**Step 1: Stage and commit**

```bash
git add scripts/abstract_loader.py scripts/sample_oncology.py scripts/run_batch_grading.py scripts/generate_review.py
git add docs/session-notes/2026-03-04-scale-experiment-api-review.md
git commit -m "grade: add sampling, batch grading, and expert review scripts

- abstract_loader.py: shared utility for RePORTER abstract zips
- sample_oncology.py: stratified NCI sampling + abstract join
- run_batch_grading.py: batch grading with JSONL checkpoint/resume
- generate_review.py: standalone HTML expert review (anti-anchoring)
- Session notes documenting API performance findings"
```

---

### Task 6: Update CLAUDE.md and README.md

Update project documentation to reflect current state.

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`

**Step 1: Update CLAUDE.md**

Minimal factual updates only:
- Models: GPT-4.1-mini replaces GPT-4o-mini
- Key files: add 4 new scripts
- Commands: add sampling/grading/review commands
- Status: reflect current state

**Step 2: Update README.md**

Rewrite to describe current 3-step pipeline: Filter → Classify (LLM) → Analyze.
Remove references to `data/oct-2024/` and deleted scripts.

**Step 3: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: update CLAUDE.md and README for current pipeline state"
```

---

### Task 7: Create PR

**Step 1: Verify everything**

```bash
python3 scripts/run_calibration.py --model google/gemini-2.5-flash-lite --limit 1
python3 -c "from scripts.grader_prompt import create_grading_prompt, call_openrouter, call_openai"
python3 -c "from scripts.utils import load_env, parse_llm_json, call_with_retry"
python3 -c "from scripts.abstract_loader import load_abstracts_for_year"
```

**Step 2: Create PR**

```bash
gh pr create --title "Cleanup: remove dead code, fix API issues, add scale-up scripts" --body "$(cat <<'EOF'
## Summary
- Remove 4 dead scripts and legacy `data/oct-2024/` files
- Slim `grader_prompt.py` from 569 to ~150 lines (remove legacy prompt, dead functions)
- Extract shared utilities: `load_env()`, `parse_llm_json()`, `call_with_retry()`
- Fix critical API issues: add 60s timeout, retry with backoff, checkpoint error handling
- Add 4 new scripts: `abstract_loader.py`, `sample_oncology.py`, `run_batch_grading.py`, `generate_review.py`
- Update CLAUDE.md and README.md

## API Findings (from 2026-03-04 experiment)
- OpenRouter: fine for Gemini (4.2s/call), poor for OpenAI models (24s, 8% 502 errors)
- GPT-4.1-mini replaces GPT-4o-mini (better instruction-following, comparable cost)
- For production 270K run: use OpenAI Batch API + Google Vertex Batch (not serial)

## Test plan
- [ ] `run_calibration.py --limit 1` passes with slimmed grader_prompt.py
- [ ] All imports resolve (no broken references to removed files)
- [ ] `run_batch_grading.py --limit 3` grades successfully with retry logic
- [ ] `generate_review.py` produces valid HTML
- [ ] README accurately describes current pipeline

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Design Decisions (to document in session notes, NOT in CLAUDE.md)

These are architectural decisions made during the 2026-03-04 session:

1. **OpenRouter is a routing proxy, not a batch processor.** Its value is model comparison and fallback routing. For single-model batch runs, direct provider APIs are faster and more reliable. For production, use OpenAI Batch API (50% cheaper) and Google Vertex Batch.

2. **JSONL > JSON for streaming results.** One record per line enables: append-mode writes, crash-safe checkpointing, line-counting for progress, and `grep`/`jq` for ad-hoc queries. JSON arrays require holding everything in memory.

3. **Error records should NOT mark IDs as "done."** Transient failures (502, timeout) should be retriable. The checkpoint should distinguish `succeeded` from `errored`, with a `--retry-errors` flag to re-process failures.

4. **GPT-4.1-mini over GPT-4o-mini.** Better instruction-following (49% vs 29% on OpenAI evals), 1M token context (vs 128K), slightly higher cost ($0.40/$1.60 vs $0.15/$0.60 per M tokens) but negligible at our scale.

5. **Serial API calls are fine for experiments (<5K grants).** For the full 270K run, build a separate `run_batch_api.py` that uses provider batch endpoints. Don't over-engineer the serial script.

---

## Execution Order

| Task | Dependencies | Est. time |
|------|-------------|-----------|
| Task 1: Extract utils | — | 5 min |
| Task 2: Fix API issues | Task 1 (imports utils) | 10 min |
| Task 3: Slim grader_prompt.py | — | 5 min |
| Task 4: Remove dead scripts | — | 3 min |
| Task 5: Stage new scripts | — | 2 min |
| Task 6: Update docs | Tasks 1-5 complete | 10 min |
| Task 7: Create PR | Task 6 | 2 min |

Tasks 1-5 can be done in any order (no cross-dependencies except Task 2 importing from Task 1's `utils.py`). Task 6 should come last so docs reflect the final state.
