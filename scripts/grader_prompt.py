"""
NIH Biomarker Project — Grader prompt construction and API helpers.

Library module imported by ``run_calibration.py`` and ``run_batch_grading.py``.
No ``__main__`` block; not intended to be run directly.
"""

import json
from pathlib import Path


# ---------------------------------------------------------------------------
# Rubric loading and system prompt construction
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_PREAMBLE = (
    "You are an expert biomedical research methodologist classifying "
    "NIH-funded biomarker research projects.\n\n"
    "Your task is to classify each project on THREE dimensions based on "
    "the title and abstract."
)

_SYSTEM_PROMPT_OUTPUT_FORMAT = """
## Output Format

You MUST respond with valid JSON matching this exact schema:

```json
{
  "biomarker_use": {
    "primary": "<code from Dimension 1>",
    "secondary": "<code from Dimension 1 or null>",
    "confidence": "<high|medium|low>"
  },
  "research_design": {
    "primary": "<code from Dimension 2>",
    "secondary": "<code from Dimension 2 or null>",
    "confidence": "<high|medium|low>"
  },
  "evidence_strength": {
    "code": "<code from Dimension 3>",
    "confidence": "<high|medium|low>"
  },
  "key_phrases": [
    "<exact quote from abstract supporting biomarker_use classification>",
    "<exact quote from abstract supporting research_design classification>",
    "<exact quote from abstract supporting evidence_strength classification>"
  ],
  "reasoning": "<1-2 sentences explaining the classification>"
}
```

IMPORTANT:
- Use ONLY codes defined in the rubric above
- key_phrases must be EXACT quotes from the abstract
- If uncertain between categories, use the more conservative code (correlational > causal, prognostic_risk > prognostic_efficacy, predictive_ambiguous > predictive_enrichment > predictive_optimal)
"""


def load_rubric(path: Path | None = None) -> str:
    """Read the classification rubric from data/RUBRIC.md.

    Parameters
    ----------
    path : Path or None
        Explicit path to the rubric file. When *None* (the default), the path
        is resolved relative to this script's location:
        ``<repo>/data/RUBRIC.md``.

    Returns
    -------
    str
        The full text content of the rubric file.
    """
    if path is None:
        path = Path(__file__).resolve().parent.parent / "data" / "RUBRIC.md"
    return Path(path).read_text(encoding="utf-8")


def _strip_rubric_for_prompt(rubric_text: str) -> str:
    """Remove documentation-only sections from rubric before prompt injection."""
    lines = rubric_text.split("\n")
    filtered = []
    skip = False
    for line in lines:
        # Skip the "SOURCE OF TRUTH" preamble
        if line.startswith("> **SOURCE OF TRUTH**"):
            continue
        # Skip References section
        if line.startswith("## References"):
            skip = True
            continue
        if skip and line.startswith("## "):
            skip = False
        if not skip:
            filtered.append(line)
    return "\n".join(filtered)


def build_system_prompt(rubric_text: str) -> str:
    """Construct the full system prompt from rubric text.

    The prompt is assembled from three pieces:
    1. A preamble describing the classifier's role.
    2. The rubric text (loaded from ``data/RUBRIC.md``), with
       documentation-only sections stripped.
    3. Output-format instructions and classification rules.
    """
    rubric_text = _strip_rubric_for_prompt(rubric_text)
    return f"{_SYSTEM_PROMPT_PREAMBLE}\n\n{rubric_text}\n{_SYSTEM_PROMPT_OUTPUT_FORMAT}"


# ---------------------------------------------------------------------------
# Prompt templates and construction
# ---------------------------------------------------------------------------

USER_PROMPT_TEMPLATE = """Classify this NIH biomarker research project:

**Title:** {title}

**Abstract:** {abstract}

Return ONLY the JSON classification."""


def create_grading_prompt(title: str, abstract: str) -> list:
    """Create the messages for the grading API call."""
    system_prompt = build_system_prompt(load_rubric())
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": USER_PROMPT_TEMPLATE.format(title=title, abstract=abstract),
        },
    ]


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------


def call_openrouter(messages: list, model: str, api_key: str) -> dict:
    """Call OpenRouter API."""
    import urllib.request

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 500,
    }

    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/nih-biomarker-funding",
            "X-Title": "NIH Biomarker Grader",
        },
    )

    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read())

    return result


def call_openai(messages: list, model: str, api_key: str) -> dict:
    """Call OpenAI API directly."""
    import urllib.request

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 500,
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read())

    return result
