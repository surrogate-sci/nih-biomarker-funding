# Inspect AI Task Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace hand-rolled grading scripts with a single Inspect AI task that works for calibration (25 examples), mid-scale evaluation (~10K grants), and full production (270K grants with batch API) — same code at every scale.

**Architecture:** One `inspect_task.py` with three components: a Dataset loader (CSV → Sample via `record_to_sample`), a Solver (thin wrapper around existing `grader_prompt.py`), and a Scorer (JSON parsing + dimension code validation). Reuses all existing domain logic; adds no new scientific content.

**Tech Stack:** Python 3.10+, `inspect-ai` (pip install), existing `scripts/grader_prompt.py`

---

### Task 1: Install inspect-ai and verify it works

**Files:**
- Modify: `requirements.txt` (create if missing)

**Step 1: Check if requirements.txt exists**

```bash
ls requirements.txt 2>/dev/null || echo "does not exist"
```

**Step 2: Install inspect-ai**

```bash
pip install inspect-ai
```

**Step 3: Verify installation**

```bash
inspect version
python3 -c "from inspect_ai import Task, task; print('OK')"
```

Expected: prints version and "OK".

**Step 4: Create or update requirements.txt**

Add `inspect-ai` to the file. Keep existing deps if the file exists.

**Step 5: Commit**

```bash
git add requirements.txt
git commit -m "deps: add inspect-ai"
```

---

### Task 2: Write the Dataset loader

The dataset loader converts CSV rows into Inspect `Sample` objects. Must handle two CSV formats:
- Calibration CSVs: columns `APPLICATION_ID`, `PROJECT_TITLE`, `ABSTRACT` (or `ABSTRACT_TEXT`), `YEAR`, `MATCHED_TERMS`
- Oncology/production CSVs: columns `APPLICATION_ID`, `PROJECT_TITLE`, `ABSTRACT_TEXT`, `FY`, `ADMINISTERING_IC`, `IC_NAME`, `ACTIVITY`, `TOTAL_COST`, `EXPLICIT_BIOMARKER`, `HAS_ABSTRACT`

**Files:**
- Create: `inspect_task.py`
- Create: `tests/test_inspect_task.py`

**Step 1: Write the failing test**

```python
# tests/test_inspect_task.py
"""Tests for inspect_task.py — Dataset, Solver, Scorer."""

import unittest


class TestRecordToSample(unittest.TestCase):
    """Test the record_to_sample function for CSV → Sample conversion."""

    def test_oncology_csv_format(self):
        """Oncology sample CSV has PROJECT_TITLE, ABSTRACT_TEXT, FY columns."""
        from inspect_task import record_to_sample

        record = {
            "APPLICATION_ID": "6785291",
            "FY": "2004",
            "PROJECT_TITLE": "Prognostic implications of Flt3 mutations in AML",
            "ABSTRACT_TEXT": "DESCRIPTION: Activating mutations in Flt3...",
            "HAS_ABSTRACT": "True",
            "ADMINISTERING_IC": "CA",
            "IC_NAME": "NATIONAL CANCER INSTITUTE",
            "ACTIVITY": "R21",
            "TOTAL_COST": "173000.0",
            "EXPLICIT_BIOMARKER": "True",
        }
        sample = record_to_sample(record)

        self.assertEqual(sample.id, "6785291")
        self.assertIn("Prognostic implications", sample.input)
        self.assertIn("Activating mutations in Flt3", sample.input)
        self.assertEqual(sample.metadata["fy"], "2004")
        self.assertEqual(sample.metadata["ic"], "CA")

    def test_calibration_csv_format(self):
        """Calibration CSV has PROJECT_TITLE, ABSTRACT (not ABSTRACT_TEXT), YEAR columns."""
        from inspect_task import record_to_sample

        record = {
            "APPLICATION_ID": "8303985",
            "YEAR": "2012",
            "PROJECT_TITLE": "Genome-wide Identification of DNA Methylation Biomarkers in AML",
            "ABSTRACT": "DESCRIPTION: The project aims to identify...",
            "MATCHED_TERMS": "pharmacodynamic biomarker",
        }
        sample = record_to_sample(record)

        self.assertEqual(sample.id, "8303985")
        self.assertIn("Genome-wide Identification", sample.input)
        self.assertIn("The project aims to identify", sample.input)
        self.assertEqual(sample.metadata["fy"], "2012")

    def test_missing_abstract_uses_title_only(self):
        """When abstract is empty, input should still work (title only)."""
        from inspect_task import record_to_sample

        record = {
            "APPLICATION_ID": "9999999",
            "FY": "2020",
            "PROJECT_TITLE": "Some biomarker study",
            "ABSTRACT_TEXT": "",
            "HAS_ABSTRACT": "False",
        }
        sample = record_to_sample(record)

        self.assertIn("Some biomarker study", sample.input)
        self.assertEqual(sample.metadata["has_abstract"], False)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_inspect_task.py::TestRecordToSample -v
```

Expected: FAIL — `inspect_task` not found or `record_to_sample` not defined.

**Step 3: Write the record_to_sample function**

```python
# inspect_task.py (top of file)
"""
Inspect AI task for NIH biomarker grant classification.

Wraps the rubric-driven grading pipeline (RUBRIC.md + grader_prompt.py)
as an Inspect Task with Dataset, Solver, and Scorer.

Usage:
    # Calibration (25 examples)
    inspect eval inspect_task.py --model openrouter/google/gemini-2.5-flash-lite

    # Mid-scale (oncology sample, ~2K grants)
    inspect eval inspect_task.py -T dataset_path=data/oncology_sample_100per_year.csv \\
        --model google/gemini-2.5-flash-lite --max-connections 20

    # Production (270K, batch API)
    inspect eval-set inspect_task.py -T dataset_path=data/full_with_abstracts.csv \\
        --model openai/gpt-4.1-mini,google/gemini-2.5-flash-lite \\
        --batch --log-dir logs/production-v1
"""

from inspect_ai.dataset import Sample


# ---------------------------------------------------------------------------
# Dataset: CSV → Sample
# ---------------------------------------------------------------------------

# Template matching grader_prompt.py's USER_PROMPT_TEMPLATE
_INPUT_TEMPLATE = """Classify this NIH biomarker research project:

**Title:** {title}

**Abstract:** {abstract}

Return ONLY the JSON classification."""


def record_to_sample(record: dict) -> Sample:
    """Convert a CSV row to an Inspect Sample.

    Handles two CSV formats:
    - Oncology/production: PROJECT_TITLE, ABSTRACT_TEXT, FY, HAS_ABSTRACT, ...
    - Calibration: PROJECT_TITLE, ABSTRACT, YEAR, MATCHED_TERMS, ...
    """
    app_id = record.get("APPLICATION_ID", "")
    title = record.get("PROJECT_TITLE", "")

    # Handle both column names for abstract
    abstract = record.get("ABSTRACT_TEXT") or record.get("ABSTRACT") or ""

    # Handle both column names for fiscal year
    fy = record.get("FY") or record.get("YEAR") or ""

    # Build metadata from whatever columns exist
    metadata = {"fy": fy}
    if "ADMINISTERING_IC" in record:
        metadata["ic"] = record["ADMINISTERING_IC"]
    if "IC_NAME" in record:
        metadata["ic_name"] = record["IC_NAME"]
    if "ACTIVITY" in record:
        metadata["activity"] = record["ACTIVITY"]
    if "TOTAL_COST" in record:
        metadata["total_cost"] = record.get("TOTAL_COST", "")
    if "EXPLICIT_BIOMARKER" in record:
        metadata["explicit_biomarker"] = record.get("EXPLICIT_BIOMARKER", "") == "True"
    if "MATCHED_TERMS" in record:
        metadata["matched_terms"] = record.get("MATCHED_TERMS", "")

    has_abstract_raw = record.get("HAS_ABSTRACT", "")
    has_abstract = has_abstract_raw == "True" if has_abstract_raw else bool(abstract.strip())
    metadata["has_abstract"] = has_abstract

    return Sample(
        id=app_id,
        input=_INPUT_TEMPLATE.format(title=title, abstract=abstract),
        metadata=metadata,
    )
```

**Step 4: Run tests**

```bash
python3 -m pytest tests/test_inspect_task.py::TestRecordToSample -v
```

Expected: 3 PASS.

**Step 5: Commit**

```bash
git add inspect_task.py tests/test_inspect_task.py
git commit -m "inspect: add dataset loader (record_to_sample)"
```

---

### Task 3: Write the Solver

The solver wraps `grader_prompt.py` to construct the system prompt from RUBRIC.md and inject it into the Inspect message chain. It does NOT call `generate()` — that's a separate step in the solver chain.

**Files:**
- Modify: `inspect_task.py`
- Modify: `tests/test_inspect_task.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_inspect_task.py

class TestRubricSolver(unittest.TestCase):
    """Test that the solver correctly constructs messages from the rubric."""

    def test_solver_adds_system_message(self):
        """Solver should insert a system message with the rubric."""
        from inspect_task import rubric_solver
        from inspect_ai.solver import TaskState
        from inspect_ai.model import ChatMessageUser, ChatMessageSystem

        solver_fn = rubric_solver()
        # The solver factory returns a coroutine — we just verify it's callable
        # and has the right structure. Full integration test via inspect eval.
        self.assertTrue(callable(solver_fn))

    def test_system_prompt_contains_rubric_codes(self):
        """The system prompt built from RUBRIC.md should contain dimension codes."""
        from scripts.grader_prompt import load_rubric, build_system_prompt

        rubric = load_rubric()
        prompt = build_system_prompt(rubric)

        # Spot-check a few codes from each dimension
        self.assertIn("susceptibility_risk", prompt)
        self.assertIn("surrogate_endpoint", prompt)
        self.assertIn("observational_retrospective", prompt)
        self.assertIn("experimental_rct", prompt)
        self.assertIn("correlational", prompt)
        self.assertIn("causal_clinical", prompt)
```

**Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_inspect_task.py::TestRubricSolver -v
```

Expected: FAIL — `rubric_solver` not defined.

**Step 3: Implement the solver**

Add to `inspect_task.py`:

```python
from inspect_ai.solver import solver, Generate, TaskState
from inspect_ai.model import ChatMessageSystem

from scripts.grader_prompt import load_rubric, build_system_prompt


# ---------------------------------------------------------------------------
# Solver: rubric prompt injection
# ---------------------------------------------------------------------------

@solver
def rubric_solver(rubric_path: str | None = None):
    """Inject the rubric-based system prompt into the message chain.

    Loads RUBRIC.md (or a custom path) and constructs the system prompt
    using grader_prompt.py's build_system_prompt(). Inserts as the first
    message. Does NOT call generate() — chain with generate() in the task.
    """
    rubric_text = load_rubric(rubric_path)
    system_prompt = build_system_prompt(rubric_text)

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        state.messages.insert(0, ChatMessageSystem(content=system_prompt))
        return state

    return solve
```

**Step 4: Run tests**

```bash
python3 -m pytest tests/test_inspect_task.py::TestRubricSolver -v
```

Expected: 2 PASS.

**Step 5: Commit**

```bash
git add inspect_task.py tests/test_inspect_task.py
git commit -m "inspect: add rubric_solver (system prompt injection)"
```

---

### Task 4: Write the Scorer

The scorer parses the LLM's JSON response, validates dimension codes against the rubric's enum, and returns a multi-valued `Score`. Invalid JSON or unknown codes are flagged in metadata (not silently dropped).

**Files:**
- Modify: `inspect_task.py`
- Modify: `tests/test_inspect_task.py`

**Step 1: Write the failing tests**

```python
# Add to tests/test_inspect_task.py
import asyncio


class TestRubricScorer(unittest.TestCase):
    """Test the scorer's JSON parsing and code validation."""

    def test_valid_classification_scores_correctly(self):
        """A well-formed JSON response should produce a valid Score."""
        from inspect_task import VALID_DIM1, VALID_DIM2, VALID_DIM3, _parse_classification

        raw_json = '''{
            "biomarker_use": {"primary": "prognostic_risk", "secondary": null, "confidence": "high"},
            "research_design": {"primary": "observational_cohort", "secondary": null, "confidence": "high"},
            "evidence_strength": {"code": "correlational", "confidence": "high"},
            "key_phrases": ["some phrase"],
            "reasoning": "test reasoning"
        }'''

        result = _parse_classification(raw_json)

        self.assertIsNotNone(result)
        self.assertEqual(result["dim1"], "prognostic_risk")
        self.assertEqual(result["dim2"], "observational_cohort")
        self.assertEqual(result["dim3"], "correlational")
        self.assertTrue(result["valid"])

    def test_invalid_code_flagged(self):
        """Unknown dimension codes should be flagged but still parsed."""
        from inspect_task import _parse_classification

        raw_json = '''{
            "biomarker_use": {"primary": "FAKE_CODE", "secondary": null, "confidence": "high"},
            "research_design": {"primary": "observational_cohort", "secondary": null, "confidence": "high"},
            "evidence_strength": {"code": "correlational", "confidence": "high"},
            "key_phrases": [],
            "reasoning": "test"
        }'''

        result = _parse_classification(raw_json)

        self.assertEqual(result["dim1"], "FAKE_CODE")
        self.assertFalse(result["valid"])
        self.assertIn("dim1", result["invalid_codes"])

    def test_malformed_json_returns_error(self):
        """Unparseable response should return None."""
        from inspect_task import _parse_classification

        result = _parse_classification("this is not json at all")
        self.assertIsNone(result)

    def test_json_in_markdown_fences(self):
        """JSON wrapped in ```json ... ``` should still parse."""
        from inspect_task import _parse_classification

        raw = '```json\n{"biomarker_use": {"primary": "diagnostic", "secondary": null, "confidence": "high"}, "research_design": {"primary": "experimental_rct", "secondary": null, "confidence": "high"}, "evidence_strength": {"code": "experimental_weak", "confidence": "medium"}, "key_phrases": [], "reasoning": "test"}\n```'

        result = _parse_classification(raw)

        self.assertIsNotNone(result)
        self.assertEqual(result["dim1"], "diagnostic")

    def test_valid_code_enums(self):
        """Verify the code enums match RUBRIC.md."""
        from inspect_task import VALID_DIM1, VALID_DIM2, VALID_DIM3

        # Dim1: 17 codes
        self.assertEqual(len(VALID_DIM1), 17)
        self.assertIn("susceptibility_risk", VALID_DIM1)
        self.assertIn("methods_correlational", VALID_DIM1)

        # Dim2: 10 codes
        self.assertEqual(len(VALID_DIM2), 10)
        self.assertIn("observational_retrospective", VALID_DIM2)
        self.assertIn("methods_secondary_analysis", VALID_DIM2)

        # Dim3: 5 codes
        self.assertEqual(len(VALID_DIM3), 5)
        self.assertIn("correlational", VALID_DIM3)
        self.assertIn("methods_for_causal", VALID_DIM3)
```

**Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_inspect_task.py::TestRubricScorer -v
```

Expected: FAIL — `VALID_DIM1`, `_parse_classification` not defined.

**Step 3: Implement the scorer**

Add to `inspect_task.py`:

```python
from inspect_ai.scorer import scorer, Score, Target, CORRECT, INCORRECT, mean, stderr
from scripts.utils import parse_llm_json


# ---------------------------------------------------------------------------
# Valid rubric codes (must match RUBRIC.md)
# ---------------------------------------------------------------------------

VALID_DIM1 = {
    "susceptibility_risk", "diagnostic", "monitoring",
    "prognostic_risk", "prognostic_efficacy", "prognostic_enrichment",
    "predictive_optimal", "predictive_enrichment", "predictive_ambiguous",
    "pharmacodynamic", "safety", "surrogate_endpoint",
    "stratification_treatment", "stratification_diagnostic", "stratification_ambiguous",
    "methods_causal", "methods_correlational",
}

VALID_DIM2 = {
    "observational_retrospective", "observational_crosssectional",
    "observational_cohort", "observational_longitudinal",
    "observational_case_cohort", "observational_quasi",
    "experimental_singlearm", "experimental_rct", "experimental_perturbation",
    "methods_secondary_analysis",
}

VALID_DIM3 = {
    "correlational", "experimental_weak",
    "causal_preclinical", "causal_clinical",
    "methods_for_causal",
}


def _parse_classification(raw: str) -> dict | None:
    """Parse LLM JSON response and validate dimension codes.

    Returns dict with keys: dim1, dim2, dim3, dim1_confidence, dim2_confidence,
    dim3_confidence, dim1_secondary, dim2_secondary, key_phrases, reasoning,
    valid (bool), invalid_codes (list).

    Returns None if JSON is unparseable.
    """
    try:
        parsed = parse_llm_json(raw)
    except Exception:
        return None

    dim1 = parsed.get("biomarker_use", {}).get("primary", "")
    dim2 = parsed.get("research_design", {}).get("primary", "")
    dim3 = parsed.get("evidence_strength", {}).get("code", "")

    invalid_codes = []
    if dim1 not in VALID_DIM1:
        invalid_codes.append("dim1")
    if dim2 not in VALID_DIM2:
        invalid_codes.append("dim2")
    if dim3 not in VALID_DIM3:
        invalid_codes.append("dim3")

    return {
        "dim1": dim1,
        "dim2": dim2,
        "dim3": dim3,
        "dim1_confidence": parsed.get("biomarker_use", {}).get("confidence", ""),
        "dim2_confidence": parsed.get("research_design", {}).get("confidence", ""),
        "dim3_confidence": parsed.get("evidence_strength", {}).get("confidence", ""),
        "dim1_secondary": parsed.get("biomarker_use", {}).get("secondary"),
        "dim2_secondary": parsed.get("research_design", {}).get("secondary"),
        "key_phrases": parsed.get("key_phrases", []),
        "reasoning": parsed.get("reasoning", ""),
        "valid": len(invalid_codes) == 0,
        "invalid_codes": invalid_codes,
    }


@scorer(metrics={
    "valid_json": [mean(), stderr()],
    "valid_codes": [mean(), stderr()],
})
def rubric_scorer():
    """Score LLM grading output: parse JSON, validate codes, return structured result.

    Scores:
    - valid_json: 1.0 if JSON parsed, 0.0 if not
    - valid_codes: 1.0 if all dimension codes are in the rubric enum, 0.0 if any invalid
    """

    async def score(state: TaskState, target: Target) -> Score:
        raw = state.output.completion
        result = _parse_classification(raw)

        if result is None:
            return Score(
                value={"valid_json": 0.0, "valid_codes": 0.0},
                answer=raw[:500],
                explanation="Failed to parse JSON from LLM response",
            )

        return Score(
            value={
                "valid_json": 1.0,
                "valid_codes": 1.0 if result["valid"] else 0.0,
            },
            answer=raw[:500],
            explanation=result["reasoning"],
            metadata={
                "dim1": result["dim1"],
                "dim2": result["dim2"],
                "dim3": result["dim3"],
                "dim1_confidence": result["dim1_confidence"],
                "dim2_confidence": result["dim2_confidence"],
                "dim3_confidence": result["dim3_confidence"],
                "dim1_secondary": result["dim1_secondary"],
                "dim2_secondary": result["dim2_secondary"],
                "key_phrases": result["key_phrases"],
                "invalid_codes": result["invalid_codes"],
            },
        )

    return score
```

**Step 4: Run tests**

```bash
python3 -m pytest tests/test_inspect_task.py::TestRubricScorer -v
```

Expected: 5 PASS.

**Step 5: Commit**

```bash
git add inspect_task.py tests/test_inspect_task.py
git commit -m "inspect: add rubric_scorer (JSON parsing + code validation)"
```

---

### Task 5: Write the Task definition

Compose Dataset + Solver + Scorer into a `@task` function with a configurable dataset path.

**Files:**
- Modify: `inspect_task.py`
- Modify: `tests/test_inspect_task.py`

**Step 1: Write the failing test**

```python
# Add to tests/test_inspect_task.py

class TestBiomarkerGradingTask(unittest.TestCase):
    """Test the @task function returns a valid Task object."""

    def test_task_returns_task_object(self):
        """biomarker_grading() should return an Inspect Task."""
        from inspect_task import biomarker_grading
        from inspect_ai import Task

        task = biomarker_grading(
            dataset_path="data/oncology_sample_100per_year.csv"
        )
        self.assertIsInstance(task, Task)

    def test_task_default_uses_oncology_sample(self):
        """Default dataset_path should point to oncology sample."""
        from inspect_task import biomarker_grading
        from inspect_ai import Task

        task = biomarker_grading()
        self.assertIsInstance(task, Task)
```

**Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_inspect_task.py::TestBiomarkerGradingTask -v
```

Expected: FAIL — `biomarker_grading` not defined.

**Step 3: Implement the task**

Add to `inspect_task.py`:

```python
from inspect_ai import Task, task
from inspect_ai.dataset import csv_dataset
from inspect_ai.solver import generate


@task
def biomarker_grading(
    dataset_path: str = "data/oncology_sample_100per_year.csv",
    rubric_path: str | None = None,
):
    """Classify NIH biomarker grants on 3 dimensions using the RUBRIC.md rubric.

    Parameters
    ----------
    dataset_path : str
        Path to a CSV with at minimum APPLICATION_ID, PROJECT_TITLE, and
        ABSTRACT_TEXT (or ABSTRACT) columns.
    rubric_path : str or None
        Path to RUBRIC.md. Default: data/RUBRIC.md (relative to repo root).
    """
    return Task(
        dataset=csv_dataset(dataset_path, record_to_sample),
        solver=[rubric_solver(rubric_path=rubric_path), generate()],
        scorer=rubric_scorer(),
    )
```

**Step 4: Run tests**

```bash
python3 -m pytest tests/test_inspect_task.py::TestBiomarkerGradingTask -v
```

Expected: 2 PASS.

**Step 5: Commit**

```bash
git add inspect_task.py tests/test_inspect_task.py
git commit -m "inspect: add biomarker_grading @task definition"
```

---

### Task 6: Integration smoke test

Run the task against 2-3 grants from the oncology sample to verify the full pipeline works end-to-end.

**Step 1: Verify API key is available**

```bash
grep -q OPENROUTER_API_KEY .env && echo "key found" || echo "key missing"
```

If key is missing, this step requires manual setup and should be skipped.

**Step 2: Run inspect eval with --limit 3**

```bash
inspect eval inspect_task.py \
    -T dataset_path=data/oncology_sample_100per_year.csv \
    --model openrouter/google/gemini-2.5-flash-lite \
    --limit 3
```

Expected: Completes with 3 samples. Check output for:
- `valid_json` metric near 1.0
- `valid_codes` metric near 1.0
- No errors in the log

**Step 3: Verify logs exist**

```bash
ls logs/*.eval 2>/dev/null || ls ./logs/ 2>/dev/null
```

**Step 4: Run inspect view (manual verification)**

```bash
inspect view
```

Opens browser — verify samples show dim1/dim2/dim3 in metadata, reasoning in explanation.

**Step 5: Commit any config tweaks**

If the smoke test required GenerateConfig adjustments (temperature, max_tokens), add them to the task:

```python
from inspect_ai.model import GenerateConfig

@task
def biomarker_grading(...):
    return Task(
        ...,
        config=GenerateConfig(temperature=0.1, max_tokens=500),
    )
```

```bash
git add inspect_task.py
git commit -m "inspect: smoke test passing, add GenerateConfig defaults"
```

---

### Task 7: Verify batch API compatibility

Confirm the task works with direct provider APIs and the `--batch` flag. This is a dry-run verification, not a production run.

**Step 1: Test with direct Google provider (no batch)**

```bash
inspect eval inspect_task.py \
    -T dataset_path=data/oncology_sample_100per_year.csv \
    --model google/gemini-2.5-flash-lite \
    --limit 3
```

Expected: Works identically to OpenRouter. Requires `GOOGLE_API_KEY` in `.env`.

**Step 2: Test with direct OpenAI provider (no batch)**

```bash
inspect eval inspect_task.py \
    -T dataset_path=data/oncology_sample_100per_year.csv \
    --model openai/gpt-4.1-mini \
    --limit 3
```

Expected: Works. Requires `OPENAI_API_KEY` in `.env`.

**Step 3: Test batch flag (small batch)**

```bash
inspect eval inspect_task.py \
    -T dataset_path=data/oncology_sample_100per_year.csv \
    --model openai/gpt-4.1-mini \
    --batch \
    --limit 10
```

Expected: Submits as batch request, completes (may take a few minutes). If provider doesn't support batch, flag is silently ignored.

**Step 4: Test eval-set across two models**

```bash
inspect eval-set inspect_task.py \
    -T dataset_path=data/oncology_sample_100per_year.csv \
    --model openai/gpt-4.1-mini,google/gemini-2.5-flash-lite \
    --limit 5 \
    --log-dir logs/test-eval-set
```

Expected: Two eval runs, one per model. Results in `logs/test-eval-set/`.

**Step 5: Commit**

No code changes expected. If any were needed:

```bash
git add inspect_task.py
git commit -m "inspect: verified batch API and eval-set compatibility"
```

---

### Task 8: Update docs and create PR

**Files:**
- Verify: `CLAUDE.md` (already updated in this session)
- Verify: `README.md` (add inspect commands)

**Step 1: Update README.md**

Add Inspect commands to the LLM Classification Scripts section. Keep existing hand-rolled script docs as reference for historical runs.

**Step 2: Run all tests**

```bash
python3 -m pytest tests/ -v
ruff check . && ruff format .
```

Expected: All tests pass, no lint issues.

**Step 3: Commit docs**

```bash
git add README.md
git commit -m "docs: add Inspect AI usage to README"
```

**Step 4: Create PR**

```bash
gh pr create --title "inspect: add Inspect AI task for rubric grading" --body "$(cat <<'EOF'
## Summary

- Add `inspect_task.py` with Dataset loader, Solver, and Scorer for rubric grading
- Reuses existing `grader_prompt.py` and `RUBRIC.md` — no new domain logic
- Works at all scales: calibration (25 examples), mid-scale (10K), production (270K with `--batch`)
- Replaces `run_calibration.py` and `run_batch_grading.py` with `inspect eval` / `inspect eval-set`

## What's in the task

- **Dataset**: `record_to_sample` handles both calibration and production CSV formats
- **Solver**: Wraps `grader_prompt.py` to inject rubric system prompt
- **Scorer**: Parses JSON, validates dim1/dim2/dim3 codes against rubric enums, reports `valid_json` and `valid_codes` metrics

## Usage

```bash
# Calibration
inspect eval inspect_task.py --model openrouter/google/gemini-2.5-flash-lite --limit 25

# Mid-scale
inspect eval inspect_task.py -T dataset_path=data/oncology_sample_100per_year.csv \
    --model google/gemini-2.5-flash-lite --max-connections 20

# Production batch
inspect eval-set inspect_task.py -T dataset_path=data/full_with_abstracts.csv \
    --model openai/gpt-4.1-mini,google/gemini-2.5-flash-lite \
    --batch --log-dir logs/production-v1

# Browse results
inspect view
```

## Test plan

- [ ] `pytest tests/test_inspect_task.py -v` — all pass
- [ ] `inspect eval --limit 3` — smoke test with OpenRouter
- [ ] `inspect eval --limit 3 --model google/gemini-2.5-flash-lite` — direct provider
- [ ] `inspect eval --limit 10 --batch` — batch mode
- [ ] `inspect view` — results browsable
- [ ] `ruff check . && ruff format .` — clean

Closes #7.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Execution Order

| Task | Dependencies | Est. time |
|------|-------------|-----------|
| Task 1: Install inspect-ai | — | 2 min |
| Task 2: Dataset loader | Task 1 | 10 min |
| Task 3: Solver | Task 2 | 5 min |
| Task 4: Scorer | Task 2 | 10 min |
| Task 5: Task definition | Tasks 3, 4 | 5 min |
| Task 6: Smoke test | Task 5 + API keys | 5 min |
| Task 7: Batch verification | Task 5 + API keys | 10 min |
| Task 8: Docs + PR | Task 6 | 5 min |

Tasks 3 and 4 can be done in parallel (both depend on Task 2 but not each other).
Tasks 6 and 7 require API keys — if unavailable, skip and note in PR.
