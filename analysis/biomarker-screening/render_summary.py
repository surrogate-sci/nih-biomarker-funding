#!/usr/bin/env python3
"""Render SUMMARY.md from template + funding_analysis.json.

Pipeline: analyze.py → funding_analysis.json → render_summary.py → SUMMARY.md

Audit checks flag inconsistencies before writing. Exit non-zero if audit fails.
"""

import json
import re
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ANALYSIS_DIR = Path(__file__).resolve().parent
CHARTS_DIR = ANALYSIS_DIR / "charts"
JSON_PATH = CHARTS_DIR / "funding_analysis.json"
TEMPLATE_PATH = ANALYSIS_DIR / "SUMMARY.md.template"
OUTPUT_PATH = ANALYSIS_DIR / "SUMMARY.md"


def load_results() -> dict:
    if not JSON_PATH.exists():
        print(f"ERROR: {JSON_PATH} not found. Run analyze.py first.")
        sys.exit(1)
    with open(JSON_PATH) as f:
        return json.load(f)


def render(results: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(str(ANALYSIS_DIR)),
        keep_trailing_newline=True,
    )
    template = env.get_template("SUMMARY.md.template")
    return template.render(**results)


def audit(rendered: str, results: dict) -> list[str]:
    """Check rendered SUMMARY.md for inconsistencies. Returns list of warnings."""
    warnings = []

    # 1. No unrendered placeholders
    placeholders = re.findall(r"\{\{.*?\}\}", rendered)
    if placeholders:
        warnings.append(f"Unrendered placeholders found: {placeholders[:5]}")

    # 2. All chart images referenced exist
    chart_refs = re.findall(r"!\[.*?\]\(charts/(.+?)\)", rendered)
    for chart_file in chart_refs:
        if not (CHARTS_DIR / chart_file).exists():
            warnings.append(f"Chart file missing: charts/{chart_file}")

    # 3. No NaN or negative funding values in rendered text
    if "nan" in rendered.lower() or "$-" in rendered:
        warnings.append("NaN or negative values detected in rendered text")

    # 4. Summary numbers are plausible
    summary = results.get("summary", {})
    total_grants = summary.get("total_grants", 0)
    if total_grants == 0:
        warnings.append("Total grants is 0 — empty dataset?")
    total_funding = summary.get("total_funding_billions", 0)
    if total_funding <= 0:
        warnings.append(f"Total funding is ${total_funding}B — implausible")

    # 5. Unique terms should be > 0
    unique_terms = summary.get("unique_terms_matched", 0)
    if unique_terms == 0:
        warnings.append("No unique terms matched — MATCHED_TERMS column may be empty")

    return warnings


def main():
    results = load_results()
    rendered = render(results)

    warnings = audit(rendered, results)
    if warnings:
        print("AUDIT WARNINGS:")
        for w in warnings:
            print(f"  - {w}")
        print(f"\n{len(warnings)} warning(s). SUMMARY.md NOT written.")
        print("Fix the issues and re-run, or inspect funding_analysis.json.")
        sys.exit(1)

    OUTPUT_PATH.write_text(rendered)
    print(f"SUMMARY.md written to {OUTPUT_PATH}")
    print(f"  {len(rendered):,} chars, {rendered.count(chr(10)):,} lines")


if __name__ == "__main__":
    main()
