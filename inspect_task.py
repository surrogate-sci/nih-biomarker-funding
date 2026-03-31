"""
Inspect AI task for NIH biomarker grant classification.

Wraps the existing grading pipeline (scripts/grader_prompt.py, scripts/utils.py)
in Inspect's Task/Solver/Scorer framework for batch evaluation with caching,
multi-model comparison, and structured logging.

Usage:
    inspect eval inspect_task.py --model openrouter/google/gemini-2.5-flash-lite --limit 25
    inspect eval inspect_task.py --model google/gemini-2.5-flash-lite --max-connections 20
    inspect eval-set inspect_task.py --model openai/gpt-4.1-mini,google/gemini-2.5-flash-lite
"""

import json
import re
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import Sample, csv_dataset
from inspect_ai.model import ChatMessageSystem, GenerateConfig
from inspect_ai.scorer import (
    Score,
    Target,
    mean,
    scorer,
    stderr,
)
from inspect_ai.solver import TaskState, generate, solver

from scripts.grader_prompt import USER_PROMPT_TEMPLATE, build_system_prompt, load_rubric
from scripts.utils import parse_llm_json

# ---------------------------------------------------------------------------
# Parse valid classification codes from RUBRIC.md
# ---------------------------------------------------------------------------

_CODE_RE = re.compile(r"^\*\*`([a-z_]+)`\*\*\s+—")
"""Matches lines like: **`susceptibility_risk`** — Assign when..."""

_DIM_HEADER_RE = re.compile(r"^## Dimension (\d+):")
"""Matches section headers like: ## Dimension 1: Intended Biomarker Use"""


def parse_rubric_codes(rubric_path: Path | None = None) -> dict[int, set[str]]:
    """Parse valid classification codes from RUBRIC.md.

    Returns a dict mapping dimension number (1, 2, 3) to the set of valid
    codes defined under that dimension's ``## Dimension N:`` header.
    """
    path = rubric_path or Path("data/RUBRIC.md")
    text = path.read_text(encoding="utf-8")

    codes: dict[int, set[str]] = {}
    current_dim: int | None = None

    for line in text.splitlines():
        dim_match = _DIM_HEADER_RE.match(line)
        if dim_match:
            current_dim = int(dim_match.group(1))
            codes.setdefault(current_dim, set())
            continue

        # Any non-dimension ## header (Decision Hierarchy, Mapping, etc.)
        # ends the current dimension's code section.
        if line.startswith("## ") and not _DIM_HEADER_RE.match(line):
            current_dim = None
            continue

        if current_dim is not None:
            code_match = _CODE_RE.match(line)
            if code_match:
                codes[current_dim].add(code_match.group(1))

    return codes


_RUBRIC_CODES = parse_rubric_codes()

VALID_DIM1: set[str] = _RUBRIC_CODES.get(1, set())
VALID_DIM2: set[str] = _RUBRIC_CODES.get(2, set())
VALID_DIM3: set[str] = _RUBRIC_CODES.get(3, set())

# ---------------------------------------------------------------------------
# Input template (must match USER_PROMPT_TEMPLATE in grader_prompt.py)
# ---------------------------------------------------------------------------

_INPUT_TEMPLATE = USER_PROMPT_TEMPLATE


# ---------------------------------------------------------------------------
# Task 2: Dataset loader
# ---------------------------------------------------------------------------


def record_to_sample(record: dict) -> Sample:
    """Convert a CSV row to an Inspect Sample.

    Handles two CSV formats:
    - Oncology sample: FY, APPLICATION_ID, ADMINISTERING_IC, IC_NAME, ACTIVITY,
      TOTAL_COST, EXPLICIT_BIOMARKER, PROJECT_TITLE, ABSTRACT_TEXT, HAS_ABSTRACT
    - Calibration: YEAR, APPLICATION_ID, ADMINISTERING_IC, ACTIVITY, TOTAL_COST,
      PROJECT_TITLE, ABSTRACT, MATCHED_TERMS
    """
    title = record.get("PROJECT_TITLE", "")
    # Support both column names for abstract text
    abstract = record.get("ABSTRACT_TEXT") or record.get("ABSTRACT") or ""

    input_text = _INPUT_TEMPLATE.format(title=title, abstract=abstract)

    # Fiscal year: oncology uses FY, calibration uses YEAR
    fy = record.get("FY") or record.get("YEAR") or ""

    metadata: dict = {}
    if fy:
        metadata["fy"] = str(fy)
    if record.get("ADMINISTERING_IC"):
        metadata["ic"] = record["ADMINISTERING_IC"]
    if record.get("IC_NAME"):
        metadata["ic_name"] = record["IC_NAME"]
    if record.get("ACTIVITY"):
        metadata["activity"] = record["ACTIVITY"]
    if record.get("TOTAL_COST"):
        metadata["total_cost"] = record["TOTAL_COST"]
    metadata["explicit_biomarker"] = record.get("EXPLICIT_BIOMARKER", "") == "True"
    if record.get("MATCHED_TERMS"):
        metadata["matched_terms"] = record["MATCHED_TERMS"]
    if "HAS_ABSTRACT" in record:
        metadata["has_abstract"] = record["HAS_ABSTRACT"] == "True"
    else:
        metadata["has_abstract"] = bool(abstract.strip())

    # Gold labels: if the CSV has GOLD_DIM1/DIM2/DIM3 columns, pack them into
    # Sample.target so reference-based scorers can compare against expert labels.
    gold = {}
    for col, key in [
        ("GOLD_DIM1", "dim1"),
        ("GOLD_DIM2", "dim2"),
        ("GOLD_DIM3", "dim3"),
    ]:
        if record.get(col):
            gold[key] = record[col]
    target = json.dumps(gold) if gold else ""

    return Sample(
        input=input_text,
        id=record.get("APPLICATION_ID", ""),
        target=target,
        metadata=metadata if metadata else None,
    )


# ---------------------------------------------------------------------------
# Task 3: Solver
# ---------------------------------------------------------------------------


@solver
def rubric_solver(rubric_path: str | None = None):
    """Inject the RUBRIC.md system prompt into the conversation.

    Loads the rubric via ``scripts.grader_prompt.load_rubric()`` and builds
    the full system prompt via ``build_system_prompt()``. The system prompt
    is inserted as the first message. Does NOT call generate().
    """
    path = Path(rubric_path) if rubric_path else None
    rubric_text = load_rubric(path)
    system_prompt = build_system_prompt(rubric_text)

    async def solve(state: TaskState, generate_fn) -> TaskState:
        state.messages.insert(0, ChatMessageSystem(content=system_prompt))
        return state

    return solve


# ---------------------------------------------------------------------------
# Task 4: Scorer
# ---------------------------------------------------------------------------


def _validate_codes(parsed: dict) -> list[str]:
    """Check dimension codes in the parsed classification against enum sets.

    Returns a list of invalid dimension names (e.g., ``["dim1", "dim3"]``).
    An empty list means all codes are valid.
    """
    invalid: list[str] = []

    dim1_primary = parsed.get("biomarker_use", {}).get("primary", "")
    dim1_secondary = parsed.get("biomarker_use", {}).get("secondary")
    dim2_primary = parsed.get("research_design", {}).get("primary", "")
    dim2_secondary = parsed.get("research_design", {}).get("secondary")
    dim3_code = parsed.get("evidence_strength", {}).get("code", "")

    if dim1_primary not in VALID_DIM1:
        invalid.append("dim1")
    if dim1_secondary and dim1_secondary not in VALID_DIM1 and "dim1" not in invalid:
        invalid.append("dim1")
    if dim2_primary not in VALID_DIM2:
        invalid.append("dim2")
    if dim2_secondary and dim2_secondary not in VALID_DIM2 and "dim2" not in invalid:
        invalid.append("dim2")
    if dim3_code not in VALID_DIM3:
        invalid.append("dim3")

    return invalid


def _parse_classification(raw: str) -> dict | None:
    """Parse LLM classification JSON, then validate dimension codes.

    Returns a dict with the following keys on success:
    - All original parsed keys (biomarker_use, research_design, etc.)
    - ``valid``: bool indicating whether all codes are in the enum sets
    - ``invalid_codes``: list of dimension names with invalid codes

    Returns None if the JSON is malformed or cannot be extracted.
    """
    try:
        parsed = parse_llm_json(raw)
    except Exception:
        return None

    if parsed is None or not isinstance(parsed, dict):
        return None

    invalid_codes = _validate_codes(parsed)
    parsed["valid"] = len(invalid_codes) == 0
    parsed["invalid_codes"] = invalid_codes
    return parsed


@scorer(metrics={"valid_json": [mean(), stderr()], "valid_codes": [mean(), stderr()]})
def rubric_scorer():
    """Score LLM classifications against the rubric code enums.

    Produces a multi-valued Score with:
    - value: dict with ``valid_json`` (1.0/0.0) and ``valid_codes`` (1.0/0.0)
    - metadata: dim1, dim2, dim3 codes, confidences, key_phrases, reasoning,
      and ``invalid_codes`` listing which dimensions had bad codes
    """

    async def score(state: TaskState, target: Target) -> Score:
        if not state.output or not state.output.completion:
            return Score(
                value={"valid_json": 0.0, "valid_codes": 0.0},
                explanation="No model output",
            )

        raw = state.output.completion
        parsed = _parse_classification(raw)

        if parsed is None:
            return Score(
                value={"valid_json": 0.0, "valid_codes": 0.0},
                explanation="Failed to parse JSON from response",
            )

        codes_valid = parsed["valid"]
        invalid_codes = parsed["invalid_codes"]

        # Extract classification details for metadata
        dim1 = parsed.get("biomarker_use", {})
        dim2 = parsed.get("research_design", {})
        dim3 = parsed.get("evidence_strength", {})

        score_metadata = {
            "invalid_codes": invalid_codes,
            "dim1_primary": dim1.get("primary"),
            "dim1_secondary": dim1.get("secondary"),
            "dim1_confidence": dim1.get("confidence"),
            "dim2_primary": dim2.get("primary"),
            "dim2_secondary": dim2.get("secondary"),
            "dim2_confidence": dim2.get("confidence"),
            "dim3_code": dim3.get("code"),
            "dim3_confidence": dim3.get("confidence"),
            "key_phrases": parsed.get("key_phrases"),
            "reasoning": parsed.get("reasoning"),
        }

        return Score(
            value={"valid_json": 1.0, "valid_codes": 1.0 if codes_valid else 0.0},
            explanation=(
                "Valid classification"
                if codes_valid
                else f"Invalid codes in: {', '.join(invalid_codes)}"
            ),
            metadata=score_metadata,
        )

    return score


# ---------------------------------------------------------------------------
# Task 5: Task definition
# ---------------------------------------------------------------------------


@task
def biomarker_grading(
    dataset_path: str = "data/oncology_sample_100per_year.csv",
    rubric_path: str | None = None,
) -> Task:
    """Inspect AI task for NIH biomarker grant classification.

    Composes:
    1. csv_dataset with record_to_sample for input mapping
    2. rubric_solver to inject the system prompt
    3. generate() for the LLM call
    4. rubric_scorer to validate the JSON output

    Parameters
    ----------
    dataset_path : str
        Path to the CSV file with grant data.
    rubric_path : str or None
        Path to RUBRIC.md. None uses the default location.
    """
    return Task(
        dataset=csv_dataset(
            csv_file=dataset_path,
            sample_fields=record_to_sample,
        ),
        solver=[rubric_solver(rubric_path=rubric_path), generate()],
        scorer=rubric_scorer(),
        config=GenerateConfig(),
    )
