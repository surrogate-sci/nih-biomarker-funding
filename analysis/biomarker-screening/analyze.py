#!/usr/bin/env python3
"""Biomarker Screening Analysis — descriptive statistics and charts.

Reads the unified NIH biomarker dataset and produces:
- Funding over time (total vs explicit biomarker)
- Top institutes by funding
- Grant mechanism breakdown
- Explicit biomarker adoption rate

Uses Datawrapper if DATAWRAPPER_API_TOKEN is set, else seaborn/matplotlib.
Outputs: charts/ directory + funding_analysis.json
"""
import json
import sys
from pathlib import Path

# Ensure analysis dir is on path for local imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

from charts import get_renderer
from utils import DATA_QUALITY_YEARS, activity_category, load_dataset

CHARTS_DIR = Path(__file__).parent / "charts"


def funding_over_time(df: pd.DataFrame, renderer) -> dict:
    """Compute and plot funding over time."""
    yearly = df.groupby("FY").agg(
        total_funding=("TOTAL_COST", "sum"),
        grant_count=("APPLICATION_ID", "count"),
    ).reset_index()

    explicit_yearly = df[df["EXPLICIT_BIOMARKER"]].groupby("FY")["TOTAL_COST"].sum()
    yearly["explicit_funding"] = yearly["FY"].map(explicit_yearly).fillna(0)
    yearly["expanded_only_funding"] = yearly["total_funding"] - yearly["explicit_funding"]

    renderer.stacked_area(
        yearly,
        x="FY",
        y_cols=["explicit_funding", "expanded_only_funding"],
        labels=["Core terms (4)", "Expanded terms only (+6)"],
        title="NIH Biomarker-Related Funding by Keyword Match Type (FY2004\u20132024)",
        filename="funding_over_time.png",
        vlines=sorted(DATA_QUALITY_YEARS),
    )

    return {
        "years": yearly["FY"].tolist(),
        "total_funding": yearly["total_funding"].tolist(),
        "explicit_funding": yearly["explicit_funding"].tolist(),
        "grant_count": yearly["grant_count"].tolist(),
    }


def top_institutes(df: pd.DataFrame, renderer, n: int = 15) -> dict:
    """Compute and plot top institutes by funding."""
    ic = (
        df.groupby(["ADMINISTERING_IC", "IC_NAME"])
        .agg(
            total_funding=("TOTAL_COST", "sum"),
            grant_count=("APPLICATION_ID", "count"),
        )
        .reset_index()
        .sort_values("total_funding", ascending=False)
        .head(n)
    )

    renderer.horizontal_bar(
        ic,
        x="total_funding",
        y="ADMINISTERING_IC",
        title=f"Top {n} NIH Institutes by Biomarker-Related Funding",
        filename="top_institutes.png",
        annotations="grant_count",
    )

    return {
        "institutes": ic[
            ["ADMINISTERING_IC", "IC_NAME", "total_funding", "grant_count"]
        ].to_dict(orient="records")
    }


def mechanism_breakdown(df: pd.DataFrame, renderer) -> dict:
    """Compute and plot grant mechanism breakdown over time."""
    df = df.copy()
    df["category"] = df["ACTIVITY"].apply(activity_category)

    cat_year = df.groupby(["FY", "category"]).agg(
        total_funding=("TOTAL_COST", "sum"),
    ).reset_index()

    pivot = cat_year.pivot_table(
        index="FY", columns="category", values="total_funding", fill_value=0
    )

    renderer.area_by_category(
        pivot,
        title="Biomarker Funding by Grant Mechanism Category (FY2004\u20132024)",
        filename="mechanism_breakdown.png",
    )

    overall = (
        df.groupby("category")
        .agg(
            total_funding=("TOTAL_COST", "sum"),
            grant_count=("APPLICATION_ID", "count"),
        )
        .sort_values("total_funding", ascending=False)
        .reset_index()
    )

    return {"categories": overall.to_dict(orient="records")}


def explicit_adoption(df: pd.DataFrame, renderer) -> dict:
    """Plot explicit biomarker term adoption rate over time."""
    yearly = df.groupby("FY").agg(
        total=("APPLICATION_ID", "count"),
        explicit=("EXPLICIT_BIOMARKER", "sum"),
    ).reset_index()
    yearly["pct_explicit"] = 100.0 * yearly["explicit"] / yearly["total"]

    renderer.line(
        yearly,
        x="FY",
        y="pct_explicit",
        title="Adoption of Explicit 'Biomarker' Terminology in NIH Grants",
        filename="explicit_adoption.png",
        ylabel="% Grants Using Core Biomarker Terms",
        ylim=(0, 100),
        vlines=sorted(DATA_QUALITY_YEARS),
    )

    return {
        "years": yearly["FY"].tolist(),
        "pct_explicit": yearly["pct_explicit"].round(1).tolist(),
    }


def main():
    print("Loading dataset...")
    df = load_dataset()
    print(f"  {len(df):,} grants loaded")

    assert abs(len(df) - 269_630) < 200, f"Unexpected row count: {len(df)}"
    total_b = df["TOTAL_COST"].sum()
    print(f"  Total funding: ${total_b / 1e9:.2f}B")

    renderer = get_renderer(CHARTS_DIR)
    print(f"  Using {renderer.backend} renderer\n")

    results = {}
    print("1. Funding over time...")
    results["funding_over_time"] = funding_over_time(df, renderer)

    print("\n2. Top institutes...")
    results["top_institutes"] = top_institutes(df, renderer)

    print("\n3. Grant mechanism breakdown...")
    results["mechanism_breakdown"] = mechanism_breakdown(df, renderer)

    print("\n4. Explicit biomarker adoption...")
    results["explicit_adoption"] = explicit_adoption(df, renderer)

    results["summary"] = {
        "total_grants": len(df),
        "explicit_grants": int(df["EXPLICIT_BIOMARKER"].sum()),
        "total_funding_billions": round(df["TOTAL_COST"].sum() / 1e9, 2),
        "explicit_funding_billions": round(
            df[df["EXPLICIT_BIOMARKER"]]["TOTAL_COST"].sum() / 1e9, 2
        ),
        "year_range": [int(df["FY"].min()), int(df["FY"].max())],
        "data_quality_years": sorted(DATA_QUALITY_YEARS),
        "renderer": renderer.backend,
    }

    out_path = CHARTS_DIR / "funding_analysis.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
