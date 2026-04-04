#!/usr/bin/env python3
"""Biomarker Screening Analysis — dataset characterization.

Produces 5 charts:
1. Total biomarker spending over time (core vs expanded stacked)
2. Funding allocation by institute (top 10, with core/expanded split)
3. Funding by keyword term (all terms with matches)
4. Keyword term × grant mechanism cross-tab
5. Keyword term trends over time

Uses Datawrapper if DATAWRAPPER_API_TOKEN is set, else seaborn/matplotlib.
Outputs: charts/ directory + funding_analysis.json
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

from charts import get_renderer
from utils import DATA_QUALITY_YEARS, activity_category, load_dataset

CHARTS_DIR = Path(__file__).parent / "charts"


def spending_over_time(df: pd.DataFrame, renderer) -> dict:
    """Chart 1: Biomarker spending per fiscal year, split by core vs expanded."""
    yearly = (
        df.groupby("FY")
        .agg(
            total_funding=("TOTAL_COST", "sum"),
            grant_count=("APPLICATION_ID", "count"),
        )
        .reset_index()
    )

    core = (
        df[df["EXPLICIT_BIOMARKER"]]
        .groupby("FY")
        .agg(
            core_funding=("TOTAL_COST", "sum"),
            core_count=("APPLICATION_ID", "count"),
        )
        .reset_index()
    )

    yearly = yearly.merge(core, on="FY", how="left").fillna(0)
    yearly["expanded_funding"] = yearly["total_funding"] - yearly["core_funding"]
    yearly["expanded_count"] = yearly["grant_count"] - yearly["core_count"]

    renderer.spending_over_time(yearly, "spending_over_time.png")

    return {
        "years": yearly["FY"].tolist(),
        "total_funding": yearly["total_funding"].tolist(),
        "core_funding": yearly["core_funding"].tolist(),
        "expanded_funding": yearly["expanded_funding"].tolist(),
        "grant_count": yearly["grant_count"].tolist(),
    }


def institute_allocation(df: pd.DataFrame, renderer, n: int = 10) -> dict:
    """Chart 2: Top institutes by total biomarker funding, with core/expanded split."""
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

    core_ic = (
        df[df["EXPLICIT_BIOMARKER"]]
        .groupby("ADMINISTERING_IC")
        .agg(core_funding=("TOTAL_COST", "sum"), core_count=("APPLICATION_ID", "count"))
        .reset_index()
    )
    ic = ic.merge(core_ic, on="ADMINISTERING_IC", how="left").fillna(0)
    ic["expanded_funding"] = ic["total_funding"] - ic["core_funding"]
    ic["expanded_count"] = ic["grant_count"] - ic["core_count"]
    ic["core_pct"] = (100 * ic["core_funding"] / ic["total_funding"]).round(1)

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
            [
                "ADMINISTERING_IC",
                "label",
                "total_funding",
                "grant_count",
                "core_funding",
                "core_pct",
            ]
        ].to_dict(orient="records")
    }


def term_funding(df: pd.DataFrame, renderer) -> dict:
    """Chart 3: Funding by keyword term (all terms that matched).

    Explodes MATCHED_TERMS so a grant matching multiple terms appears in each.
    Shows every term with at least 1 match.
    """
    # Explode MATCHED_TERMS
    exploded = df[["APPLICATION_ID", "TOTAL_COST", "MATCHED_TERMS"]].copy()
    exploded = exploded[exploded["MATCHED_TERMS"].notna() & (exploded["MATCHED_TERMS"] != "")]
    exploded["term"] = exploded["MATCHED_TERMS"].str.split(";")
    exploded = exploded.explode("term")
    exploded["term"] = exploded["term"].str.strip()
    exploded = exploded[exploded["term"] != ""]

    term_stats = (
        exploded.groupby("term")
        .agg(
            total_funding=("TOTAL_COST", "sum"),
            grant_count=("APPLICATION_ID", "count"),
        )
        .reset_index()
        .sort_values("total_funding", ascending=False)
    )

    renderer.term_funding(term_stats, "term_funding.png")

    return {"terms": term_stats.to_dict(orient="records")}


def term_by_mechanism(df: pd.DataFrame, renderer) -> dict:
    """Chart 4: Keyword term × grant mechanism cross-tabulation.

    Shows which grant mechanisms fund which keyword terms.
    Explodes MATCHED_TERMS so multi-term grants count in each term row.
    """
    work = df[["APPLICATION_ID", "TOTAL_COST", "MATCHED_TERMS", "ACTIVITY"]].copy()
    work = work[work["MATCHED_TERMS"].notna() & (work["MATCHED_TERMS"] != "")]
    work["mechanism"] = work["ACTIVITY"].apply(activity_category)
    work["term"] = work["MATCHED_TERMS"].str.split(";")
    work = work.explode("term")
    work["term"] = work["term"].str.strip()
    work = work[work["term"] != ""]

    cross = (
        work.groupby(["term", "mechanism"])
        .agg(
            total_funding=("TOTAL_COST", "sum"),
            grant_count=("APPLICATION_ID", "count"),
        )
        .reset_index()
    )

    # Pivot: rows = term, columns = mechanism
    pivot_funding = cross.pivot(
        index="term", columns="mechanism", values="total_funding"
    ).fillna(0)

    pivot_count = cross.pivot(
        index="term", columns="mechanism", values="grant_count"
    ).fillna(0)

    # Order rows by total funding descending
    row_totals = pivot_funding.sum(axis=1).sort_values(ascending=False)
    pivot_funding = pivot_funding.loc[row_totals.index]
    pivot_count = pivot_count.loc[row_totals.index]

    # Column order: largest mechanism first
    col_order = pivot_funding.sum().sort_values(ascending=False).index.tolist()
    pivot_funding = pivot_funding[col_order]
    pivot_count = pivot_count[col_order]

    # Compute R-grant percentage for each term
    r_col = "Research (R)" if "Research (R)" in pivot_funding.columns else None
    r_pct = {}
    if r_col:
        for term in pivot_funding.index:
            total = pivot_funding.loc[term].sum()
            r_pct[term] = round(100 * pivot_funding.loc[term, r_col] / total, 1) if total > 0 else 0

    renderer.term_by_mechanism(pivot_funding, pivot_count, "term_by_mechanism.png")

    return {
        "funding": {
            t: {m: float(pivot_funding.loc[t, m]) for m in pivot_funding.columns}
            for t in pivot_funding.index
        },
        "r_grant_pct": r_pct,
    }


def term_over_time(df: pd.DataFrame, renderer, terms: list = None) -> dict:
    """Chart 5: Selected keyword terms over time.

    Shows funding trends for surrogacy/response terms vs discovery terms.
    If terms is None, picks the most interesting ones automatically.
    """
    # Explode
    work = df[["APPLICATION_ID", "FY", "TOTAL_COST", "MATCHED_TERMS"]].copy()
    work = work[work["MATCHED_TERMS"].notna() & (work["MATCHED_TERMS"] != "")]
    work["term"] = work["MATCHED_TERMS"].str.split(";")
    work = work.explode("term")
    work["term"] = work["term"].str.strip()
    work = work[work["term"] != ""]

    if terms is None:
        # Show terms relevant to the hypothesis + top discovery terms for context
        terms = [
            "biomarker",
            "surrogate endpoint",
            "intermediate outcome",
            "response to therapy",
            "risk stratification",
            "companion diagnostic",
            "endophenotype",
            "genetic marker",
        ]

    work = work[work["term"].isin(terms)]

    yearly = work.groupby(["FY", "term"])["TOTAL_COST"].sum().reset_index()
    pivot = yearly.pivot(index="FY", columns="term", values="TOTAL_COST").fillna(0)

    # Order columns by total funding
    col_order = pivot.sum().sort_values(ascending=False).index.tolist()
    pivot = pivot[col_order]

    renderer.term_over_time(pivot, "term_over_time.png")

    return {
        "years": pivot.index.tolist(),
        "terms": {col: pivot[col].tolist() for col in pivot.columns},
    }


def main():
    print("Loading dataset...")
    df = load_dataset()
    print(f"  {len(df):,} grants loaded")

    total_b = df["TOTAL_COST"].sum()
    print(f"  Total funding: ${total_b / 1e9:.2f}B")
    print(f"  EXPLICIT_BIOMARKER=TRUE: {df['EXPLICIT_BIOMARKER'].sum():,}")

    # Report term coverage
    exploded = df["MATCHED_TERMS"].dropna().str.split(";").explode().str.strip()
    exploded = exploded[exploded != ""]
    unique_terms = exploded.unique()
    print(f"  Unique terms in MATCHED_TERMS: {len(unique_terms)}")
    print(f"  Term counts:")
    for term, count in exploded.value_counts().items():
        print(f"    {term:40s} {count:>8,}")

    renderer = get_renderer(CHARTS_DIR)
    print(f"\n  Using {renderer.backend} renderer\n")

    results = {}

    print("1. Total biomarker spending over time...")
    results["spending_over_time"] = spending_over_time(df, renderer)

    print("\n2. Institute allocation...")
    results["institute_allocation"] = institute_allocation(df, renderer)

    print("\n3. Funding by keyword term...")
    results["term_funding"] = term_funding(df, renderer)

    print("\n4. Term × grant mechanism...")
    results["term_by_mechanism"] = term_by_mechanism(df, renderer)

    print("\n5. Selected terms over time...")
    results["term_over_time"] = term_over_time(df, renderer)

    # Summary
    results["summary"] = {
        "total_grants": len(df),
        "total_funding_billions": round(df["TOTAL_COST"].sum() / 1e9, 2),
        "explicit_grants": int(df["EXPLICIT_BIOMARKER"].sum()),
        "unique_terms_matched": len(unique_terms),
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
