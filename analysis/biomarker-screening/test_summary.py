"""Test-driven documentation: SUMMARY.md must be consistent with data.

Run after render_summary.py to validate that SUMMARY.md accurately reflects
the current funding_analysis.json. These tests are the enforcement mechanism
for the chart registry — if someone adds a chart to SUMMARY.md without
producing it, or the dataset changes enough to invalidate the prose, tests fail.

Usage: python3 -m pytest analysis/biomarker-screening/test_summary.py -v
"""

import json
import re
from pathlib import Path

import pytest

ANALYSIS_DIR = Path(__file__).resolve().parent
CHARTS_DIR = ANALYSIS_DIR / "charts"
JSON_PATH = CHARTS_DIR / "funding_analysis.json"
SUMMARY_PATH = ANALYSIS_DIR / "SUMMARY.md"


@pytest.fixture
def summary_text():
    if not SUMMARY_PATH.exists():
        pytest.skip("SUMMARY.md not found — run render_summary.py first")
    return SUMMARY_PATH.read_text()


@pytest.fixture
def results():
    if not JSON_PATH.exists():
        pytest.skip("funding_analysis.json not found — run analyze.py first")
    with open(JSON_PATH) as f:
        return json.load(f)


def test_no_unrendered_placeholders(summary_text):
    """SUMMARY.md should have no {{ }} Jinja2 placeholders remaining."""
    placeholders = re.findall(r"\{\{.*?\}\}", summary_text)
    assert placeholders == [], f"Unrendered placeholders: {placeholders}"


def test_no_jinja_block_tags(summary_text):
    """SUMMARY.md should have no {% %} Jinja2 block tags remaining."""
    blocks = re.findall(r"\{%.*?%\}", summary_text)
    assert blocks == [], f"Unrendered block tags: {blocks}"


def test_all_registry_charts_exist(summary_text):
    """Every chart image referenced in SUMMARY.md must exist as a file."""
    chart_refs = re.findall(r"!\[.*?\]\(charts/(.+?)\)", summary_text)
    assert len(chart_refs) > 0, "No chart references found in SUMMARY.md"
    for chart_file in chart_refs:
        path = CHARTS_DIR / chart_file
        assert path.exists(), f"Chart file missing: {path}"


def test_total_grants_matches_json(summary_text, results):
    """Grant count stated in SUMMARY.md must match funding_analysis.json."""
    expected = results["summary"]["total_grants"]
    # Look for the number in the text (with commas)
    formatted = f"{expected:,}"
    assert formatted in summary_text, (
        f"Expected total grants '{formatted}' not found in SUMMARY.md"
    )


def test_funding_total_matches_json(summary_text, results):
    """Total funding in SUMMARY.md must match JSON within ±$0.5B."""
    expected = results["summary"]["total_funding_billions"]
    # Match "$175.2B" or "$175.2 billion" or "$175.22B" patterns
    amounts = re.findall(r"\$(\d+\.?\d*)\s*(?:B|billion)", summary_text)
    assert any(abs(float(a) - expected) <= 0.5 for a in amounts), (
        f"Expected ~${expected}B in SUMMARY.md, found amounts: {amounts}"
    )


def test_term_mechanism_charts_exist(results):
    """Core and expanded term × mechanism chart data must exist in JSON."""
    has_core = "core_terms_by_mechanism" in results
    has_expanded = "expanded_terms_by_mechanism" in results
    has_combined = "term_by_mechanism" in results
    assert has_core or has_expanded or has_combined, (
        "No term × mechanism data found in funding_analysis.json"
    )


def test_unique_terms_stated(summary_text, results):
    """Number of unique terms stated must match JSON."""
    expected = results["summary"].get("unique_terms_matched")
    if expected is None:
        pytest.skip("unique_terms_matched not in JSON")
    assert str(expected) in summary_text, (
        f"Expected unique terms count '{expected}' not found in SUMMARY.md"
    )


def test_no_nan_values(summary_text):
    """SUMMARY.md must not contain NaN or negative dollar amounts."""
    assert "nan" not in summary_text.lower(), "NaN found in SUMMARY.md"
    assert "$-" not in summary_text, "Negative dollar amount found in SUMMARY.md"


def test_chart_registry_has_entries(summary_text):
    """Chart registry table must have at least one entry."""
    # Look for the registry table rows (| C1 | ... |)
    registry_rows = re.findall(r"\| C\d+ \|", summary_text)
    assert len(registry_rows) >= 1, "No chart registry entries found"


def test_registry_matches_chart_refs(summary_text):
    """Every chart filename in the registry must be referenced as an image."""
    # Extract filenames from registry table
    registry_files = re.findall(r"\| C\d+ \|.*?\| `(.+?)` \|", summary_text)
    # Extract filenames from image references
    image_refs = re.findall(r"!\[.*?\]\(charts/(.+?)\)", summary_text)

    for f in registry_files:
        assert f in image_refs, (
            f"Registry chart '{f}' not shown as image in Results section"
        )
