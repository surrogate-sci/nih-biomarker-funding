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

from pathlib import Path

from inspect_ai.dataset import Sample
from inspect_ai.model import ChatMessageSystem
from inspect_ai.solver import TaskState, solver

from scripts.grader_prompt import USER_PROMPT_TEMPLATE, build_system_prompt, load_rubric

# ---------------------------------------------------------------------------
# Valid classification codes (from data/RUBRIC.md)
# ---------------------------------------------------------------------------

VALID_DIM1: set[str] = {
    "susceptibility_risk",
    "diagnostic",
    "monitoring",
    "prognostic_risk",
    "prognostic_efficacy",
    "prognostic_enrichment",
    "predictive_optimal",
    "predictive_enrichment",
    "predictive_ambiguous",
    "pharmacodynamic",
    "safety",
    "surrogate_endpoint",
    "stratification_treatment",
    "stratification_diagnostic",
    "stratification_ambiguous",
    "methods_causal",
    "methods_correlational",
}

VALID_DIM2: set[str] = {
    "observational_retrospective",
    "observational_crosssectional",
    "observational_cohort",
    "observational_longitudinal",
    "observational_case_cohort",
    "observational_quasi",
    "experimental_singlearm",
    "experimental_rct",
    "experimental_perturbation",
    "methods_secondary_analysis",
}

VALID_DIM3: set[str] = {
    "correlational",
    "experimental_weak",
    "causal_preclinical",
    "causal_clinical",
    "methods_for_causal",
}

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
    if record.get("EXPLICIT_BIOMARKER"):
        metadata["explicit_biomarker"] = record["EXPLICIT_BIOMARKER"]
    if record.get("MATCHED_TERMS"):
        metadata["matched_terms"] = record["MATCHED_TERMS"]
    if record.get("HAS_ABSTRACT"):
        metadata["has_abstract"] = record["HAS_ABSTRACT"]

    return Sample(
        input=input_text,
        id=record.get("APPLICATION_ID", ""),
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
