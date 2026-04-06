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
OUTPUT_PATH = ANALYSIS_DIR / "SUMMARY.md"


def build_context(data):
    """Build full Jinja2 context from funding_analysis.json."""
    return {
        "summary": data["summary"],
        "institute_allocation": data["institute_allocation"],
    }


def audit(rendered: str, data: dict) -> list[str]:
    """Check rendered SUMMARY.md for inconsistencies."""
    warnings = []

    placeholders = re.findall(r"\{\{.*?\}\}", rendered)
    if placeholders:
        warnings.append(f"Unrendered placeholders found: {placeholders[:5]}")

    chart_refs = re.findall(r"!\[.*?\]\(charts/(.+?)\)", rendered)
    for chart_file in chart_refs:
        if not (CHARTS_DIR / chart_file).exists():
            warnings.append(f"Chart file missing: charts/{chart_file}")

    if "nan" in rendered.lower() or "$-" in rendered:
        warnings.append("NaN or negative values detected in rendered text")

    summary = data.get("summary", {})
    if summary.get("total_grants", 0) == 0:
        warnings.append("Total grants is 0 — empty dataset?")
    if summary.get("total_funding_billions", 0) <= 0:
        warnings.append("Total funding is implausible")
    if summary.get("unique_terms_matched", 0) == 0:
        warnings.append("No unique terms matched")

    return warnings


def main():
    if not JSON_PATH.exists():
        print(f"ERROR: {JSON_PATH} not found. Run analyze.py first.")
        sys.exit(1)

    data = json.loads(JSON_PATH.read_text())
    context = build_context(data)

    env = Environment(
        loader=FileSystemLoader(str(ANALYSIS_DIR)),
        keep_trailing_newline=True,
    )
    template = env.get_template("SUMMARY.md.template")
    rendered = template.render(**context)

    warnings = audit(rendered, data)
    if warnings:
        print("AUDIT WARNINGS:")
        for w in warnings:
            print(f"  - {w}")
        print(f"\n{len(warnings)} warning(s). SUMMARY.md NOT written.")
        sys.exit(1)

    OUTPUT_PATH.write_text(rendered)
    s = data["summary"]
    print(
        f"SUMMARY.md written ({len(rendered):,} chars, {rendered.count(chr(10)):,} lines)"
    )
    print(
        f"  {s['total_grants']:,} grants, ${s['total_funding_billions']}B, {s['unique_terms_matched']} terms"
    )


if __name__ == "__main__":
    main()
