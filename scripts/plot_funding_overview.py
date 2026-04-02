"""
Quick funding overview charts from Phase 1 summary data.

Usage:
    python3 scripts/plot_funding_overview.py
    # or with venv:
    .venv/bin/python3 scripts/plot_funding_overview.py

Outputs PNGs to visualizations/.
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from pathlib import Path

# ---------------------------------------------------------------------------
# Data from data/filtered/SUMMARY.md (FY2004-2024)
# ---------------------------------------------------------------------------

YEARS = [
    2004,
    2005,
    2006,
    2007,
    2008,
    2009,
    2010,
    2011,
    2012,
    2013,
    2014,
    2015,
    2016,
    2017,
    2018,
    2019,
    2020,
    2021,
    2022,
    2023,
    2024,
]

# In billions
BIOMARKER_RELEVANT = [
    1.71,
    0.11,
    0.09,
    2.71,
    2.79,
    4.80,
    5.02,
    4.91,
    6.51,
    2.25,
    5.79,
    6.10,
    7.40,
    8.36,
    3.87,
    9.95,
    11.36,
    11.54,
    12.53,
    13.13,
    13.55,
]

EXPLICIT_BIOMARKER = [
    0.49,
    0.06,
    0.07,
    0.16,
    0.18,
    1.60,
    1.83,
    1.85,
    2.51,
    0.29,
    0.32,
    0.48,
    1.72,
    2.09,
    1.09,
    2.71,
    3.11,
    3.33,
    3.60,
    4.09,
    4.19,
]

# Years with known PROJECT_TERMS data quality issues — exclude from charts
BAD_YEARS = {2005, 2006, 2013, 2018}


def main():
    out_dir = Path(__file__).resolve().parent.parent / "visualizations"
    out_dir.mkdir(exist_ok=True)

    # Filter to clean years only
    clean = [
        (y, t, e)
        for y, t, e in zip(YEARS, BIOMARKER_RELEVANT, EXPLICIT_BIOMARKER)
        if y not in BAD_YEARS
    ]
    years = np.array([c[0] for c in clean])
    total = np.array([c[1] for c in clean])
    explicit = np.array([c[2] for c in clean])

    # Recalculate totals for clean years only
    total_sum = total.sum()
    explicit_sum = explicit.sum()
    broad_sum = total_sum - explicit_sum
    share_avg = (explicit_sum / total_sum) * 100

    # --- Chart 1: Stacked area — the specificity gap ---
    fig, ax = plt.subplots(figsize=(12, 6))

    ax.fill_between(
        years,
        0,
        explicit,
        alpha=0.8,
        color="#2e86ab",
        label=f"Explicit biomarker terms (${explicit_sum:.0f}B)",
    )
    ax.fill_between(
        years,
        explicit,
        total,
        alpha=0.5,
        color="#d4a574",
        label=f"Broad keyword match only (${broad_sum:.0f}B)",
    )

    ax.set_xlabel("NIH Fiscal Year", fontsize=12)
    ax.set_ylabel("Spending ($ Billions)", fontsize=12)
    ax.set_title(
        "NIH Biomarker-Related Research Spending, FY2004\u20132024\n"
        f"Only {share_avg:.0f}% of spending uses explicit biomarker terminology",
        fontsize=13,
        fontweight="bold",
    )
    ax.legend(loc="upper left", fontsize=10)
    ax.set_xlim(2004, 2024)
    ax.set_ylim(0, 16)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:.0f}B"))

    ax.annotate(
        "4 years excluded due to missing PROJECT_TERMS metadata (FY2005-06, FY2013, FY2018)",
        xy=(0.01, 0.01),
        xycoords="axes fraction",
        fontsize=8,
        color="#888",
        style="italic",
    )

    plt.tight_layout()
    path1 = out_dir / "funding_specificity_gap.png"
    fig.savefig(path1, dpi=150, bbox_inches="tight")
    print(f"Saved: {path1}")
    plt.close(fig)

    # --- Chart 2: Explicit biomarker share (clean years only) ---
    fig, ax = plt.subplots(figsize=(12, 5))

    share = (explicit / total) * 100

    ax.bar(years, share, color="#2e86ab", alpha=0.8, width=0.8)
    ax.axhline(
        y=share_avg,
        color="#d4574a",
        linestyle="--",
        linewidth=1.5,
        alpha=0.7,
        label=f"Average: {share_avg:.0f}%",
    )

    ax.set_xlabel("NIH Fiscal Year", fontsize=12)
    ax.set_ylabel(
        "% of Biomarker Spending Using\nExplicit Biomarker Terms", fontsize=11
    )
    ax.set_title(
        "How Specific Is NIH Biomarker Research Language?",
        fontsize=13,
        fontweight="bold",
    )
    ax.legend(loc="upper right", fontsize=10)
    ax.set_xlim(2003.2, 2024.8)
    ax.set_ylim(0, 45)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))

    plt.tight_layout()
    path2 = out_dir / "explicit_biomarker_share.png"
    fig.savefig(path2, dpi=150, bbox_inches="tight")
    print(f"Saved: {path2}")
    plt.close(fig)


if __name__ == "__main__":
    main()
