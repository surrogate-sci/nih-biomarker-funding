"""
Produce public-facing figures for surrogate-sci/biomarker-funding.

Reads per-year spending data from data/filtered/SUMMARY.md (hardcoded below
from the FY2004-2024 run), computes cumulative totals in nominal and
CPI-adjusted dollars, then UPDATES existing Datawrapper line charts and
exports their PNGs to visualizations/.

IMPORTANT: Always update existing chart IDs — never create new ones.

Datawrapper chart IDs:
  VydiG — cumulative nominal (pre-existing, canonical)
  pzYSe — cumulative 2024-dollar adjusted (created 2026-04-02, to be replaced
           with pre-existing chart ID if one exists for inflation-adjusted)

Usage:
    python3 scripts/plot_public_figures.py [--export-only]

    --export-only  Skip data upload; just re-export PNGs.

Requirements:
    pip install requests
    DATAWRAPPER_API_TOKEN set in .env (loaded via scripts/utils.py load_env())
"""

import argparse
import base64
import sys
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Source data — from data/filtered/SUMMARY.md (FY2004-2024 ExPORTER pipeline)
# ---------------------------------------------------------------------------
YEARS = [
    2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013,
    2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024,
]

# Annual spending in billions — "expanded" = all 10 biomarker terms matched
EXPANDED_ANNUAL_B = [
    1.71, 0.11, 0.09, 2.71, 2.79, 4.80, 5.02, 4.91, 6.51, 2.25,
    5.79, 6.10, 7.40, 8.36, 3.87, 9.95, 11.36, 11.54, 12.53, 13.13, 13.55,
]

# Annual spending in billions — "core" = explicit biomarker terms only (4 terms)
CORE_ANNUAL_B = [
    0.49, 0.06, 0.07, 0.16, 0.18, 1.60, 1.83, 1.85, 2.51, 0.29,
    0.32, 0.48, 1.72, 2.09, 1.09, 2.71, 3.11, 3.33, 3.60, 4.09, 4.19,
]

# Years with known PROJECT_TERMS metadata gaps in NIH ExPORTER source files
BAD_YEARS = {2005, 2006, 2013, 2018}

# ---------------------------------------------------------------------------
# BLS CPI-U annual averages — used for inflation adjustment
# Base year: 2024 (314.0)
# Source: https://www.bls.gov/cpi/tables/supplemental-files/historical-cpi-u-202501.xlsx
# ---------------------------------------------------------------------------
CPI_U = {
    2004: 188.9, 2005: 195.3, 2006: 201.6, 2007: 207.3, 2008: 215.3,
    2009: 214.5, 2010: 218.1, 2011: 224.9, 2012: 229.6, 2013: 233.0,
    2014: 236.7, 2015: 237.0, 2016: 240.0, 2017: 245.1, 2018: 251.1,
    2019: 255.7, 2020: 258.8, 2021: 270.0, 2022: 292.7, 2023: 304.7,
    2024: 314.0,
}
CPI_BASE_YEAR = 2024

# Datawrapper chart IDs — update these in place, never create new ones
DW_CHART_NOMINAL = "VydiG"   # NIH Biomarker-Related Spending (pre-existing)
DW_CHART_ADJ     = "pzYSe"   # CPI-adjusted (created 2026-04-02)

DW_API = "https://api.datawrapper.de/v3"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_token() -> str:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from utils import load_env
    load_env()
    import os
    token = os.environ.get("DATAWRAPPER_API_TOKEN")
    if not token:
        raise RuntimeError("DATAWRAPPER_API_TOKEN not found in environment / .env")
    return token


def cumulative(annual: list[float]) -> list[float]:
    totals, running = [], 0.0
    for v in annual:
        running = round(running + v, 2)
        totals.append(running)
    return totals


def inflation_adjust(annual: list[float], years: list[int], base_year: int = CPI_BASE_YEAR) -> list[float]:
    base_cpi = CPI_U[base_year]
    return [round(v * base_cpi / CPI_U[y], 2) for v, y in zip(annual, years)]


def build_csv(years, col1_annual, col2_annual, col1_label, col2_label) -> str:
    lines = [f"Fiscal Year,{col1_label},{col2_label}"]
    c1_cum, c2_cum = cumulative(col1_annual), cumulative(col2_annual)
    for y, c1, c2 in zip(years, c1_cum, c2_cum):
        lines.append(f"{y},{c1},{c2}")
    return "\n".join(lines)


def dw_upload_data(chart_id: str, csv_text: str, token: str) -> None:
    r = requests.put(
        f"{DW_API}/charts/{chart_id}/data",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "text/csv"},
        data=csv_text.encode(),
    )
    r.raise_for_status()


def dw_patch_metadata(chart_id: str, patch: dict, token: str) -> None:
    r = requests.patch(
        f"{DW_API}/charts/{chart_id}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=patch,
    )
    r.raise_for_status()


def dw_publish(chart_id: str, token: str) -> str:
    r = requests.post(
        f"{DW_API}/charts/{chart_id}/publish",
        headers={"Authorization": f"Bearer {token}"},
    )
    r.raise_for_status()
    return r.json()["data"]["publicUrl"]


def dw_export_png(chart_id: str, token: str, out_path: Path, width: int = 900) -> None:
    r = requests.post(
        f"{DW_API}/charts/{chart_id}/export/png",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"width": width, "scale": 2, "plain": False},
    )
    r.raise_for_status()
    out_path.write_bytes(r.content)
    print(f"Saved: {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-only", action="store_true",
                        help="Skip data upload; only re-export PNGs")
    args = parser.parse_args()

    token = load_token()
    out_dir = Path(__file__).resolve().parent.parent / "visualizations"
    out_dir.mkdir(exist_ok=True)

    # Adjusted annual series
    core_adj   = inflation_adjust(CORE_ANNUAL_B,     YEARS)
    expand_adj = inflation_adjust(EXPANDED_ANNUAL_B, YEARS)

    # Shared visualize patch: dots at every data point + full x/y grid
    viz_patch = {
        "metadata": {
            "visualize": {
                "x-grid": "on",
                "lines": {
                    "Core":     {"symbols": {"enabled": True}},
                    "Expanded": {"symbols": {"enabled": True}},
                },
                "line-widths": {"Core": 2.5, "Expanded": 2.5},
                "custom-colors": {"Core": "#1a6b9c", "Expanded": "#e8a85f"},
            }
        }
    }

    if not args.export_only:
        # --- Nominal chart ---
        nom_csv = build_csv(
            YEARS, CORE_ANNUAL_B, EXPANDED_ANNUAL_B,
            "Core", "Expanded",
        )
        print(f"Uploading nominal data to {DW_CHART_NOMINAL}...")
        dw_upload_data(DW_CHART_NOMINAL, nom_csv, token)
        dw_patch_metadata(DW_CHART_NOMINAL, viz_patch, token)
        url_nom = dw_publish(DW_CHART_NOMINAL, token)
        print(f"Published: {url_nom}")

        # --- Inflation-adjusted chart ---
        adj_csv = build_csv(
            YEARS, core_adj, expand_adj,
            "Core", "Expanded",
        )
        print(f"Uploading CPI-adjusted data to {DW_CHART_ADJ}...")
        dw_upload_data(DW_CHART_ADJ, adj_csv, token)
        dw_patch_metadata(DW_CHART_ADJ, viz_patch, token)
        url_adj = dw_publish(DW_CHART_ADJ, token)
        print(f"Published: {url_adj}")

    # --- Export PNGs ---
    print("Exporting PNGs...")
    dw_export_png(DW_CHART_NOMINAL, token,
                  out_dir / "cumulative_biomarker_funding_nominal.png",
                  width=1000)
    dw_export_png(DW_CHART_ADJ,    token,
                  out_dir / "cumulative_biomarker_funding_2024dollars.png",
                  width=1000)

    # Also write the combined CSV for the public repo
    csv_path = Path(__file__).resolve().parent.parent / "data" / "biomarker_funding_2004_2024_with_cpi_adjustment.csv"
    rows = ["Fiscal Year,"
            "Core Annual Nominal ($B),Core Cumulative Nominal ($B),"
            "Core Annual 2024$ ($B),Core Cumulative 2024$ ($B),"
            "Extended Annual Nominal ($B),Extended Cumulative Nominal ($B),"
            "Extended Annual 2024$ ($B),Extended Cumulative 2024$ ($B),"
            "CPI-U Annual Avg,Data Gap Flag"]
    core_cum_nom  = cumulative(CORE_ANNUAL_B)
    core_cum_adj  = cumulative(core_adj)
    ext_cum_nom   = cumulative(EXPANDED_ANNUAL_B)
    ext_cum_adj   = cumulative(expand_adj)
    for i, y in enumerate(YEARS):
        rows.append(
            f"{y},"
            f"{CORE_ANNUAL_B[i]},{core_cum_nom[i]},"
            f"{core_adj[i]},{core_cum_adj[i]},"
            f"{EXPANDED_ANNUAL_B[i]},{ext_cum_nom[i]},"
            f"{expand_adj[i]},{ext_cum_adj[i]},"
            f"{CPI_U[y]},{'Y' if y in BAD_YEARS else 'N'}"
        )
    csv_path.write_text("\n".join(rows) + "\n")
    print(f"Saved: {csv_path}")


if __name__ == "__main__":
    main()
