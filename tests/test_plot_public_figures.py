"""
Tests for scripts/plot_public_figures.py.

Validates data integrity and script logic WITHOUT touching Datawrapper
or the public repo. Run before any push:

    python3 -m pytest tests/test_plot_public_figures.py -v
"""

import sys
from pathlib import Path

import pytest

# Make scripts/ importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from plot_public_figures import (
    YEARS,
    CORE_ANNUAL_B,
    EXPANDED_ANNUAL_B,
    CPI_U,
    CPI_BASE_YEAR,
    BAD_YEARS,
    build_csv,
    cumulative,
    inflation_adjust,
)


# ---------------------------------------------------------------------------
# Source data shape
# ---------------------------------------------------------------------------

def test_years_range():
    assert YEARS[0] == 2004
    assert YEARS[-1] == 2024
    assert len(YEARS) == 21


def test_annual_series_length():
    assert len(CORE_ANNUAL_B) == len(YEARS)
    assert len(EXPANDED_ANNUAL_B) == len(YEARS)


def test_no_negative_spending():
    assert all(v >= 0 for v in CORE_ANNUAL_B), "Core annual has negative values"
    assert all(v >= 0 for v in EXPANDED_ANNUAL_B), "Expanded annual has negative values"


def test_expanded_always_gte_core():
    """Expanded keyword set must capture at least as much as core."""
    for y, c, e in zip(YEARS, CORE_ANNUAL_B, EXPANDED_ANNUAL_B):
        assert e >= c, f"FY{y}: expanded ({e}) < core ({c})"


def test_cpi_covers_all_years():
    for y in YEARS:
        assert y in CPI_U, f"CPI-U missing for {y}"


# ---------------------------------------------------------------------------
# cumulative()
# ---------------------------------------------------------------------------

def test_cumulative_monotone():
    for series, name in [(CORE_ANNUAL_B, "Core"), (EXPANDED_ANNUAL_B, "Expanded")]:
        cum = cumulative(series)
        for i in range(1, len(cum)):
            assert cum[i] >= cum[i - 1], f"{name}: cumulative decreased at index {i}"


def test_cumulative_final_totals():
    """Spot-check known totals from SUMMARY.md."""
    core_cum = cumulative(CORE_ANNUAL_B)
    ext_cum = cumulative(EXPANDED_ANNUAL_B)
    assert abs(core_cum[-1] - 35.77) < 0.01, f"Core total {core_cum[-1]} ≠ 35.77"
    assert abs(ext_cum[-1] - 134.48) < 0.01, f"Expanded total {ext_cum[-1]} ≠ 134.48"


# ---------------------------------------------------------------------------
# inflation_adjust()
# ---------------------------------------------------------------------------

def test_inflation_adjust_base_year_unchanged():
    """Base year (2024) values should be unchanged after adjustment."""
    adj = inflation_adjust(CORE_ANNUAL_B, YEARS, base_year=CPI_BASE_YEAR)
    base_idx = YEARS.index(CPI_BASE_YEAR)
    assert abs(adj[base_idx] - CORE_ANNUAL_B[base_idx]) < 0.01


def test_inflation_adjust_pre2024_inflated():
    """All years before 2024 should adjust upward (CPI < base CPI)."""
    adj = inflation_adjust(CORE_ANNUAL_B, YEARS, base_year=CPI_BASE_YEAR)
    for i, y in enumerate(YEARS):
        if y < CPI_BASE_YEAR and CORE_ANNUAL_B[i] > 0:
            assert adj[i] >= CORE_ANNUAL_B[i], \
                f"FY{y}: adjusted ({adj[i]}) < nominal ({CORE_ANNUAL_B[i]})"


# ---------------------------------------------------------------------------
# build_csv()
# ---------------------------------------------------------------------------

def test_build_csv_column_names():
    csv_text = build_csv(YEARS, CORE_ANNUAL_B, EXPANDED_ANNUAL_B, "Core", "Expanded")
    header = csv_text.splitlines()[0]
    assert header == "Fiscal Year,Core,Expanded"


def test_build_csv_row_count():
    csv_text = build_csv(YEARS, CORE_ANNUAL_B, EXPANDED_ANNUAL_B, "Core", "Expanded")
    lines = csv_text.splitlines()
    assert len(lines) == len(YEARS) + 1  # header + 21 data rows


def test_build_csv_no_missing_values():
    csv_text = build_csv(YEARS, CORE_ANNUAL_B, EXPANDED_ANNUAL_B, "Core", "Expanded")
    for line in csv_text.splitlines()[1:]:
        parts = line.split(",")
        assert len(parts) == 3, f"Wrong column count: {line}"
        assert all(p.strip() != "" for p in parts), f"Empty value in: {line}"


def test_build_csv_cumulative_monotone():
    """Values in the CSV (cumulative) must be non-decreasing."""
    csv_text = build_csv(YEARS, CORE_ANNUAL_B, EXPANDED_ANNUAL_B, "Core", "Expanded")
    rows = [line.split(",") for line in csv_text.splitlines()[1:]]
    core_vals = [float(r[1]) for r in rows]
    ext_vals  = [float(r[2]) for r in rows]
    for i in range(1, len(core_vals)):
        assert core_vals[i] >= core_vals[i - 1]
        assert ext_vals[i]  >= ext_vals[i - 1]


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

def test_datawrapper_token_loadable():
    """DATAWRAPPER_API_TOKEN must be present in environment or .env."""
    import os
    token = os.environ.get("DATAWRAPPER_API_TOKEN")
    if not token:
        # Try loading from .env in the repo root (two levels up from tests/)
        env_path = Path(__file__).resolve().parent.parent.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("DATAWRAPPER_API_TOKEN="):
                    token = line.split("=", 1)[1].strip()
                    break
    if not token:
        pytest.skip("DATAWRAPPER_API_TOKEN not available (set env var or .env)")
    assert len(token) > 10, "Token looks too short"
