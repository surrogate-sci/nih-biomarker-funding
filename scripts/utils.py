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
        fenced = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        fenced = content.split("```")[1].split("```")[0]
    else:
        fenced = content
    try:
        return json.loads(fenced.strip())
    except json.JSONDecodeError:
        # Fallback: prose around an unfenced object — slice first "{" to last "}".
        start, end = content.find("{"), content.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(content[start : end + 1])
