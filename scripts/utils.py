"""Shared utilities for NIH biomarker grading scripts."""

import json
import os
import re
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
    except json.JSONDecodeError as first_error:
        # Fallback: scan for top-level JSON objects in the full response (prose
        # around them, trailing commas, or a self-correction that emits a second
        # "Corrected JSON" object). Return the LAST complete object — the
        # model's final answer.
        cleaned = re.sub(r",\s*([}\]])", r"\1", content)
        decoder = json.JSONDecoder()
        objects, i = [], cleaned.find("{")
        while i != -1:
            try:
                obj, end = decoder.raw_decode(cleaned, i)
            except json.JSONDecodeError:
                i = cleaned.find("{", i + 1)
                continue
            if isinstance(obj, dict):
                objects.append(obj)
            i = cleaned.find("{", end)
        if not objects:
            raise first_error
        return objects[-1]
