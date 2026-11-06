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


def _strip_trailing_commas(text: str) -> str:
    """Remove commas directly before a closing } or ], ignoring JSON string contents."""
    out, in_str, esc = [], False, False
    for i, ch in enumerate(text):
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == ",":
            j = i + 1
            while j < len(text) and text[j] in " \t\r\n":
                j += 1
            if j < len(text) and text[j] in "}]":
                continue
        out.append(ch)
    return "".join(out)


def _top_level_object_spans(text: str) -> list[str]:
    """Return substrings of balanced top-level {...} blocks (string-aware).

    An unterminated block (truncated output) is not returned, so nested inner
    objects of a truncated answer are never mistaken for the answer.
    """
    spans, depth, start, in_str, esc = [], 0, -1, False, False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = depth > 0
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0:
                spans.append(text[start : i + 1])
    return spans


def _is_placeholder_echo(obj: dict) -> bool:
    """True for an echoed schema template such as {"primary": "<code from Dimension 1>"}."""
    primary = (obj.get("biomarker_use") or {}) if isinstance(obj.get("biomarker_use"), dict) else {}
    value = primary.get("primary")
    return isinstance(value, str) and value.strip().startswith("<")


def parse_llm_json(content: str, required_key: str = "biomarker_use") -> dict:
    """Parse the classification JSON object from an LLM response.

    1. A single fenced block or the whole response parses as-is: return it.
    2. Otherwise scan the full response for balanced top-level objects, strip
       trailing commas outside strings, keep dicts containing ``required_key``
       that are not echoed schema templates, and return the LAST one (Sonnet
       5.5 sometimes emits a "Correction: ... Corrected JSON:" second object).

    A truncated answer yields no balanced top-level object and raises.
    Raises json.JSONDecodeError (or ValueError) when no classification is found.
    """
    if content.count("```json") == 1:
        fenced = content.split("```json")[1].split("```")[0]
    elif content.count("```") == 2:
        fenced = content.split("```")[1].split("```")[0]
    else:
        fenced = content
    try:
        return json.loads(fenced.strip())
    except json.JSONDecodeError as first_error:
        candidates = []
        for span in _top_level_object_spans(content):
            try:
                obj = json.loads(_strip_trailing_commas(span))
            except (json.JSONDecodeError, RecursionError):
                continue
            if isinstance(obj, dict) and required_key in obj and not _is_placeholder_echo(obj):
                candidates.append(obj)
        if not candidates:
            raise first_error
        return candidates[-1]
