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
from utils import DATA_QUALITY_YEARS, grant_category, load_dataset

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


def institute_over_time(df: pd.DataFrame, renderer, n_top: int = 5) -> dict:
    """C3: Line chart — top N institutes as lines, rest as shaded Other band."""
    df = df.copy()
    df["ic_short"] = df["ADMINISTERING_IC"].map(IC_CODE_TO_NAME)
    df.loc[~df["ADMINISTERING_IC"].isin(PILOT_ICS), "ic_short"] = "Other"

    yearly_ic = df.groupby(["FY", "ic_short"])["TOTAL_COST"].sum().reset_index()
    pivot = yearly_ic.pivot(index="FY", columns="ic_short", values="TOTAL_COST").fillna(
        0
    )

    # Top N by total funding
    totals = (
        pivot.drop(columns=["Other"], errors="ignore")
        .sum()
        .sort_values(ascending=False)
    )
    top_names = totals.head(n_top).index.tolist()

    top_lines = pivot[top_names]
    other_cols = [c for c in pivot.columns if c not in top_names]
    other_band = pivot[other_cols].sum(axis=1)

    renderer.institute_over_time(top_lines, other_band, "institute_over_time.png")

    return {
        "years": pivot.index.tolist(),
        "top_institutes": {col: top_lines[col].tolist() for col in top_lines.columns},
        "other": other_band.tolist(),
    }


def category_over_time(df: pd.DataFrame, renderer) -> dict:
    """C4: Stacked area — Clinical vs Research funding over time."""
    df = df.copy()
    df["category"] = df["NIH_SPENDING_CATS"].apply(grant_category)

    yearly = df.groupby(["FY", "category"])["TOTAL_COST"].sum().reset_index()
    pivot = yearly.pivot(index="FY", columns="category", values="TOTAL_COST").fillna(0)

    # Ensure consistent column order
    for col in ["Research", "Clinical"]:
        if col not in pivot.columns:
            pivot[col] = 0.0
    pivot = pivot[["Research", "Clinical"]]

    renderer.category_over_time(pivot, "category_over_time.png")

    return {
        "years": pivot.index.tolist(),
        "categories": {col: pivot[col].tolist() for col in pivot.columns},
    }


FUNDING_THRESHOLD = 1e9  # $1B — terms below this are collapsed into "Other"


def _term_by_category(df, term_filter, filename, title, renderer):
    """Shared logic for core/expanded term × Clinical/Research charts."""
    work = df[
        ["APPLICATION_ID", "TOTAL_COST", "MATCHED_TERMS", "NIH_SPENDING_CATS"]
    ].copy()
    work = work[work["MATCHED_TERMS"].notna() & (work["MATCHED_TERMS"] != "")]
    work["category"] = work["NIH_SPENDING_CATS"].apply(grant_category)
    work["term"] = work["MATCHED_TERMS"].str.split(";")
    work = work.explode("term")
    work["term"] = work["term"].str.strip()
    work = work[work["term"] != ""]
    work = work[work["term"].isin(term_filter)]

    if work.empty:
        return {"terms": []}

    cross = (
        work.groupby(["term", "category"])
        .agg(
            total_funding=("TOTAL_COST", "sum"), grant_count=("APPLICATION_ID", "count")
        )
        .reset_index()
    )

    # Consolidate terms below threshold into "Other"
    term_totals = cross.groupby("term")["total_funding"].sum()
    big_terms = term_totals[term_totals >= FUNDING_THRESHOLD].index.tolist()
    small_terms = term_totals[term_totals < FUNDING_THRESHOLD].index.tolist()

    if small_terms:
        other_rows = cross[cross["term"].isin(small_terms)].copy()
        other_rows["term"] = f"Other ({len(small_terms)} terms)"
        other_agg = (
            other_rows.groupby(["term", "category"])
            .agg(
                total_funding=("total_funding", "sum"),
                grant_count=("grant_count", "sum"),
            )
            .reset_index()
        )
        cross = pd.concat(
            [cross[cross["term"].isin(big_terms)], other_agg], ignore_index=True
        )

    renderer.term_by_category(cross, filename, title=title)

    return {"terms": cross.to_dict(orient="records")}


def core_terms_by_category(df: pd.DataFrame, renderer) -> dict:
    """C5: Core biomarker terms — Clinical vs Research."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
    from keyword_terms import CORE_BIOMARKER_TERMS

    return _term_by_category(
        df,
        set(CORE_BIOMARKER_TERMS),
        "core_terms_by_mechanism.png",
        "Core Biomarker Terms: Clinical vs Research Funding",
        renderer,
    )


def expanded_terms_by_category(df: pd.DataFrame, renderer) -> dict:
    """C6: Expanded-only terms — Clinical vs Research."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
    from keyword_terms import CORE_BIOMARKER_TERMS, EXPANDED_BIOMARKER_TERMS

    expanded_only = set(EXPANDED_BIOMARKER_TERMS) - set(CORE_BIOMARKER_TERMS)
    return _term_by_category(
        df,
        expanded_only,
        "expanded_terms_by_mechanism.png",
        "Expanded Keyword Terms: Clinical vs Research Funding",
        renderer,
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

    print("\nC3. Institute funding over time (top 5 lines)...")
    results["institute_over_time"] = institute_over_time(df, renderer)

    print("\nC4. Clinical vs Research over time...")
    results["category_over_time"] = category_over_time(df, renderer)

    print("\nC5. Core terms: Clinical vs Research...")
    results["core_terms_by_category"] = core_terms_by_category(df, renderer)

    print("\nC6. Expanded terms: Clinical vs Research...")
    results["expanded_terms_by_category"] = expanded_terms_by_category(df, renderer)

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
