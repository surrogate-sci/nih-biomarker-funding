#!/usr/bin/env python3
"""Biomarker Screening Analysis — descriptive statistics and charts.

Reads the unified NIH biomarker dataset and produces:
1. Total biomarker spending over time (core vs expanded stacked)
2. Funding allocation by institute (top 10, with core/expanded split)
3. Funding by institute over time (stacked area, top 8 + other)
4. Explicit biomarker adoption rate over time (% grants using core terms)
5. Match source breakdown over time (keyword vs abstract-only)
6. Funding by grant mechanism (R, P, U, K, T, F, Other)
7. Funding by primary keyword term (top 15)

Uses Datawrapper if DATAWRAPPER_API_TOKEN is set, else seaborn/matplotlib.
Outputs: charts/ directory + funding_analysis.json
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

from charts import IC_CODE_TO_NAME, IC_LABELS, PILOT_ICS, get_renderer
from utils import DATA_QUALITY_YEARS, activity_category, load_dataset

CHARTS_DIR = Path(__file__).parent / "charts"


def spending_over_time(df: pd.DataFrame, renderer) -> dict:
    """Chart 1: Biomarker spending per fiscal year, split by core vs expanded."""
    # Total (all grants)
    yearly = (
        df.groupby("FY")
        .agg(
            total_funding=("TOTAL_COST", "sum"),
            grant_count=("APPLICATION_ID", "count"),
        )
        .reset_index()
    )

    # Core-only (EXPLICIT_BIOMARKER=TRUE)
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
        "core_count": [int(x) for x in yearly["core_count"].tolist()],
        "expanded_count": [int(x) for x in yearly["expanded_count"].tolist()],
    }


def institute_allocation(df: pd.DataFrame, renderer, n: int = 10) -> dict:
    """Chart 2: Top institutes by total biomarker funding, with core/expanded split."""
    # Total per institute
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

    # Core funding per institute
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

    ic["label"] = ic["ADMINISTERING_IC"].map(lambda x: IC_LABELS.get(x, x))

    renderer.institute_allocation(ic, "institute_allocation.png")

    return {
        "institutes": ic[
            [
                "ADMINISTERING_IC",
                "IC_NAME",
                "label",
                "total_funding",
                "grant_count",
                "core_funding",
                "core_count",
                "expanded_funding",
                "expanded_count",
                "core_pct",
            ]
        ].to_dict(orient="records")
    }


def institute_over_time(df: pd.DataFrame, renderer) -> dict:
    """C3: Stacked area of funding by institute over time (12 pilot ICs)."""
    df = df.copy()
    df["ic_short"] = df["ADMINISTERING_IC"].map(IC_CODE_TO_NAME)
    df.loc[~df["ADMINISTERING_IC"].isin(PILOT_ICS), "ic_short"] = "Other"

    yearly_ic = df.groupby(["FY", "ic_short"])["TOTAL_COST"].sum().reset_index()
    pivot = yearly_ic.pivot(index="FY", columns="ic_short", values="TOTAL_COST").fillna(
        0
    )

    # Order columns by total funding (largest first), Other last
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


def mechanism_over_time(df: pd.DataFrame, renderer) -> dict:
    """C4: Stacked area of funding by grant mechanism over time."""
    df = df.copy()
    df["mechanism"] = df["ACTIVITY"].apply(activity_category)

    yearly = df.groupby(["FY", "mechanism"])["TOTAL_COST"].sum().reset_index()
    pivot = yearly.pivot(index="FY", columns="mechanism", values="TOTAL_COST").fillna(0)

    # Order columns by total funding
    col_order = pivot.sum().sort_values(ascending=False).index.tolist()
    pivot = pivot[col_order]

    renderer.mechanism_over_time(pivot, "mechanism_over_time.png")

    return {
        "years": pivot.index.tolist(),
        "mechanisms": {col: pivot[col].tolist() for col in pivot.columns},
    }


def _term_by_mechanism_filtered(df, renderer, term_filter, filename, title):
    """Shared logic for core/expanded term × mechanism charts."""
    work = df[["APPLICATION_ID", "TOTAL_COST", "MATCHED_TERMS", "ACTIVITY"]].copy()
    work = work[work["MATCHED_TERMS"].notna() & (work["MATCHED_TERMS"] != "")]
    work["mechanism"] = work["ACTIVITY"].apply(activity_category)
    work["term"] = work["MATCHED_TERMS"].str.split(";")
    work = work.explode("term")
    work["term"] = work["term"].str.strip()
    work = work[work["term"] != ""]
    work = work[work["term"].isin(term_filter)]

    if work.empty:
        return {"funding": {}, "counts": {}, "r_grant_pct": {}}

    cross = (
        work.groupby(["term", "mechanism"])
        .agg(
            total_funding=("TOTAL_COST", "sum"), grant_count=("APPLICATION_ID", "count")
        )
        .reset_index()
    )

    pivot_funding = cross.pivot(
        index="term", columns="mechanism", values="total_funding"
    ).fillna(0)
    pivot_count = cross.pivot(
        index="term", columns="mechanism", values="grant_count"
    ).fillna(0)

    row_totals = pivot_funding.sum(axis=1).sort_values(ascending=False)
    pivot_funding = pivot_funding.loc[row_totals.index]
    pivot_count = pivot_count.loc[row_totals.index]

    col_order = pivot_funding.sum().sort_values(ascending=False).index.tolist()
    pivot_funding = pivot_funding[col_order]
    pivot_count = pivot_count[col_order]

    renderer.term_by_mechanism(pivot_funding, pivot_count, filename, title=title)

    r_col = "Research (R)" if "Research (R)" in pivot_funding.columns else None
    r_pct = {}
    if r_col:
        for term in pivot_funding.index:
            total = pivot_funding.loc[term].sum()
            r_pct[term] = (
                round(100 * pivot_funding.loc[term, r_col] / total, 1)
                if total > 0
                else 0
            )

    return {
        "funding": {
            t: {m: float(pivot_funding.loc[t, m]) for m in pivot_funding.columns}
            for t in pivot_funding.index
        },
        "counts": {
            t: {m: int(pivot_count.loc[t, m]) for m in pivot_count.columns}
            for t in pivot_count.index
        },
        "r_grant_pct": r_pct,
    }


def core_terms_by_mechanism(df: pd.DataFrame, renderer) -> dict:
    """C5: Core biomarker terms × grant mechanism."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
    from keyword_terms import CORE_BIOMARKER_TERMS

    return _term_by_mechanism_filtered(
        df,
        renderer,
        term_filter=set(CORE_BIOMARKER_TERMS),
        filename="core_terms_by_mechanism.png",
        title="Core Biomarker Terms by Grant Mechanism",
    )


def expanded_terms_by_mechanism(df: pd.DataFrame, renderer) -> dict:
    """C6: Expanded-only terms × grant mechanism."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
    from keyword_terms import CORE_BIOMARKER_TERMS, EXPANDED_BIOMARKER_TERMS

    expanded_only = set(EXPANDED_BIOMARKER_TERMS) - set(CORE_BIOMARKER_TERMS)
    return _term_by_mechanism_filtered(
        df,
        renderer,
        term_filter=expanded_only,
        filename="expanded_terms_by_mechanism.png",
        title="Expanded Keyword Terms by Grant Mechanism",
    )


def main():
    print("Loading dataset...")
    df = load_dataset()
    print(f"  {len(df):,} grants loaded")

    total_b = df["TOTAL_COST"].sum()
    print(f"  Total funding: ${total_b / 1e9:.2f}B")
    print(f"  EXPLICIT_BIOMARKER=TRUE: {df['EXPLICIT_BIOMARKER'].sum():,}")
    print(f"  PRIMARY_TERM populated: {(df['PRIMARY_TERM'] != '').sum():,}")

    renderer = get_renderer(CHARTS_DIR)
    print(f"  Using {renderer.backend} renderer\n")

    results = {}

    # Chart registry — only sanctioned analyses run here.
    # See SUMMARY.md template for the registry spec.
    print("C1. Spending over time (core vs expanded)...")
    results["spending_over_time"] = spending_over_time(df, renderer)

    print("\nC2. Institute allocation (12 pilot ICs)...")
    results["institute_allocation"] = institute_allocation(df, renderer, n=12)

    print("\nC3. Institute funding over time...")
    results["institute_over_time"] = institute_over_time(df, renderer)

    print("\nC4. Grant mechanisms over time...")
    results["mechanism_over_time"] = mechanism_over_time(df, renderer)

    print("\nC5. Core terms × grant mechanism...")
    results["core_terms_by_mechanism"] = core_terms_by_mechanism(df, renderer)

    print("\nC6. Expanded terms × grant mechanism...")
    results["expanded_terms_by_mechanism"] = expanded_terms_by_mechanism(df, renderer)

    # Summary stats
    explicit_df = df[df["EXPLICIT_BIOMARKER"]]
    kw_df = df[df["MATCH_SOURCE"] == "keywords_only"]
    abs_df = df[df["MATCH_SOURCE"] == "abstract_only"]

    results["summary"] = {
        "total_grants": len(df),
        "explicit_grants": int(df["EXPLICIT_BIOMARKER"].sum()),
        "expanded_only_grants": len(df) - int(df["EXPLICIT_BIOMARKER"].sum()),
        "keyword_matched_grants": len(kw_df),
        "abstract_only_grants": len(abs_df),
        "total_funding_billions": round(df["TOTAL_COST"].sum() / 1e9, 2),
        "explicit_funding_billions": round(explicit_df["TOTAL_COST"].sum() / 1e9, 2),
        "expanded_only_funding_billions": round(
            (df["TOTAL_COST"].sum() - explicit_df["TOTAL_COST"].sum()) / 1e9, 2
        ),
        "keyword_funding_billions": round(kw_df["TOTAL_COST"].sum() / 1e9, 2),
        "abstract_funding_billions": round(abs_df["TOTAL_COST"].sum() / 1e9, 2),
        "explicit_pct": round(100 * df["EXPLICIT_BIOMARKER"].mean(), 1),
        "year_range": [int(df["FY"].min()), int(df["FY"].max())],
        "data_quality_years": sorted(DATA_QUALITY_YEARS),
        "core_terms": 13,
        "expanded_terms": 36,
        "renderer": renderer.backend,
        "unique_terms_matched": len(
            df["MATCHED_TERMS"]
            .dropna()
            .str.split(";")
            .explode()
            .str.strip()
            .loc[lambda s: s != ""]
            .unique()
        ),
    }

    out_path = CHARTS_DIR / "funding_analysis.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
