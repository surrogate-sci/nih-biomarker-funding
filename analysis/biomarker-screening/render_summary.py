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

# Readable display names for AND-condition and technical terms
TERM_DISPLAY_NAMES = {
    "clinical+omics": '"clinical" and "omics" co-occurring',
    "clinical+imaging": '"clinical" and "imaging" co-occurring',
}

# Term groupings for the C3 results section.
# Each group is rendered as a labeled table. Terms are sorted by funding
# descending at render time. Terms not present in the data are skipped.
TERM_GROUPS = [
    {
        "name": "Endpoint and surrogacy terms",
        "description": "grants that explicitly name the concept of validating a biomarker as a stand-in for a clinical endpoint",
        "terms": [
            "surrogate endpoint",
            "intermediate outcome",
            "intermediate endpoint",
            "digital endpoint",
        ],
    },
    {
        "name": "Clinical decision-making terms",
        "description": "grants mentioning specific uses of biomarkers in patient care decisions",
        "terms": [
            "response to therapy",
            "risk stratification",
            "predicting response",
            "patient selection",
            "companion diagnostic",
        ],
    },
    {
        "name": "Diagnostic and prognostic terms",
        "terms": [
            "diagnostic accuracy",
            "clinical predictors",
            "prognostic value",
            "clinical diagnostics",
            "diagnostic sensitivity",
            "diagnostic specificity",
            "personalized diagnostics",
            "prognostic assays",
            "clinically actionable",
        ],
    },
    {
        "name": "Stratification and precision medicine terms",
        "terms": [
            "patient stratification",
            "precision oncology",
            "disease heterogeneity",
            "theranostics",
            "clinical subtypes",
            "disease stratification",
        ],
    },
    {
        "name": "Discovery and identification terms",
        "terms": [
            "genetic marker",
            "endophenotype",
            "imaging marker",
            "clinical marker",
            "predictive signature",
            "genomic signature",
            "biosignature",
            "proteomic signature",
            "digital biomarker",
        ],
    },
]


def _billions(val):
    """Format a dollar value for display."""
    b = val / 1e9
    if b >= 10:
        return f"${b:.1f}B"
    return f"${b:.2f}B"


def _build_term_rows(data, term_list):
    """Build sorted term rows from funding data. Skips terms with no matches."""
    funding = data["term_by_mechanism"]["funding"]
    counts = data["term_by_mechanism"]["counts"]
    r_pct = data["term_by_mechanism"]["r_grant_pct"]

    rows = []
    for term in term_list:
        if term not in funding:
            continue
        total_f = sum(funding[term].values())
        total_c = sum(counts[term].values())
        if total_c == 0:
            continue
        display = TERM_DISPLAY_NAMES.get(term, term)
        rows.append(
            {
                "display_name": display,
                "raw_term": term,
                "funding": total_f,
                "funding_str": _billions(total_f),
                "grants": total_c,
                "r_pct": r_pct.get(term, 0),
            }
        )
    rows.sort(key=lambda r: r["funding"], reverse=True)
    return rows


def build_context(data):
    """Build full Jinja2 context from funding_analysis.json."""
    term_groups = []
    for group in TERM_GROUPS:
        rows = _build_term_rows(data, group["terms"])
        if rows:
            term_groups.append(
                {
                    "name": group["name"],
                    "description": group.get("description", ""),
                    "terms": rows,
                }
            )

    return {
        "summary": data["summary"],
        "institute_allocation": data["institute_allocation"],
        "term_by_mechanism": data["term_by_mechanism"],
        "term_groups": term_groups,
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
