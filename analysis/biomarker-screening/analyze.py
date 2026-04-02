#!/usr/bin/env python3
"""Biomarker Screening Analysis — descriptive statistics and charts.

Reads the unified NIH biomarker dataset and produces:
1. Total biomarker spending over time (all keywords unified)
2. Funding allocation by institute (top 10 bar chart)
3. Funding by institute over time (stacked area, top 8 + other)

Uses Datawrapper if DATAWRAPPER_API_TOKEN is set, else seaborn/matplotlib.
Outputs: charts/ directory + funding_analysis.json
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

from charts import get_renderer
from utils import DATA_QUALITY_YEARS, load_dataset

CHARTS_DIR = Path(__file__).parent / "charts"


def spending_over_time(df: pd.DataFrame, renderer) -> dict:
    """Chart 1: Total biomarker spending per fiscal year."""
    yearly = (
        df.groupby("FY")
        .agg(
            total_funding=("TOTAL_COST", "sum"),
            grant_count=("APPLICATION_ID", "count"),
        )
        .reset_index()
    )

    renderer.spending_over_time(yearly, "spending_over_time.png")

    return {
        "years": yearly["FY"].tolist(),
        "total_funding": yearly["total_funding"].tolist(),
        "grant_count": yearly["grant_count"].tolist(),
    }


def institute_allocation(df: pd.DataFrame, renderer, n: int = 10) -> dict:
    """Chart 2: Top institutes by total biomarker funding."""
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

    # Readable labels: "NCI (Cancer)" style
    name_map = {
        "CA": "NCI (Cancer)",
        "AG": "NIA (Aging)",
        "HL": "NHLBI (Heart/Lung/Blood)",
        "AI": "NIAID (Allergy/Infectious)",
        "NS": "NINDS (Neurological)",
        "MH": "NIMH (Mental Health)",
        "DK": "NIDDK (Diabetes/Digestive)",
        "LM": "NLM (Library of Medicine)",
        "GM": "NIGMS (General Medical)",
        "EB": "NIBIB (Biomedical Imaging)",
        "ES": "NIEHS (Environmental Health)",
        "EY": "NEI (Eye)",
        "DA": "NIDA (Drug Abuse)",
        "AR": "NIAMS (Arthritis/Musculoskeletal)",
        "HD": "NICHD (Child Health)",
        "DC": "NIDCD (Deafness)",
    }
    ic["label"] = ic["ADMINISTERING_IC"].map(lambda x: name_map.get(x, x))

    renderer.institute_allocation(ic, "institute_allocation.png")

    return {
        "institutes": ic[
            ["ADMINISTERING_IC", "IC_NAME", "label", "total_funding", "grant_count"]
        ].to_dict(orient="records")
    }


def institute_over_time(df: pd.DataFrame, renderer, n_top: int = 8) -> dict:
    """Chart 3: Stacked area of funding by institute over time."""
    # Identify top N institutes by total funding
    top_ics = (
        df.groupby("ADMINISTERING_IC")["TOTAL_COST"]
        .sum()
        .nlargest(n_top)
        .index.tolist()
    )

    name_map = {
        "CA": "NCI",
        "AG": "NIA",
        "HL": "NHLBI",
        "AI": "NIAID",
        "NS": "NINDS",
        "MH": "NIMH",
        "DK": "NIDDK",
        "LM": "NLM",
    }

    df = df.copy()
    df["ic_group"] = df["ADMINISTERING_IC"].apply(
        lambda x: name_map.get(x, x) if x in top_ics else "Other"
    )

    yearly_ic = df.groupby(["FY", "ic_group"])["TOTAL_COST"].sum().reset_index()
    pivot = yearly_ic.pivot(index="FY", columns="ic_group", values="TOTAL_COST").fillna(
        0
    )

    # Order columns by total funding (largest first), but keep "Other" last
    col_order = (
        pivot.drop(columns=["Other"], errors="ignore")
        .sum()
        .sort_values(ascending=False)
        .index.tolist()
    )
    if "Other" in pivot.columns:
        col_order.append("Other")
    pivot = pivot[col_order]

    renderer.institute_over_time(pivot, "institute_over_time.png")

    return {
        "years": pivot.index.tolist(),
        "institutes": {col: pivot[col].tolist() for col in pivot.columns},
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

    print("1. Total biomarker spending over time...")
    results["spending_over_time"] = spending_over_time(df, renderer)

    print("\n2. Institute allocation...")
    results["institute_allocation"] = institute_allocation(df, renderer)

    print("\n3. Institute funding over time...")
    results["institute_over_time"] = institute_over_time(df, renderer)

    # Summary stats
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
