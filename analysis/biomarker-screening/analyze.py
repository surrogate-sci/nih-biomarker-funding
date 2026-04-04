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

from charts import get_renderer
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

    # Readable labels
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


def institute_over_time(df: pd.DataFrame, renderer, n_top: int = 8) -> dict:
    """Chart 3: Stacked area of funding by institute over time."""
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


def explicit_adoption(df: pd.DataFrame, renderer) -> dict:
    """Chart 4: % of matched grants using core biomarker terms, per fiscal year.

    Shows the trend in terminological specificity — what fraction of grants
    in the broad haystack actually use definite biomarker language.
    """
    yearly = (
        df.groupby("FY")
        .agg(
            total_count=("APPLICATION_ID", "count"),
            explicit_count=("EXPLICIT_BIOMARKER", "sum"),
        )
        .reset_index()
    )
    yearly["explicit_pct"] = (
        100 * yearly["explicit_count"] / yearly["total_count"]
    ).round(1)

    renderer.explicit_adoption(yearly, "explicit_adoption.png")

    return {
        "years": yearly["FY"].tolist(),
        "total_count": yearly["total_count"].tolist(),
        "explicit_count": [int(x) for x in yearly["explicit_count"].tolist()],
        "explicit_pct": yearly["explicit_pct"].tolist(),
    }


def match_source_breakdown(df: pd.DataFrame, renderer) -> dict:
    """Chart 5: Keyword-matched vs abstract-only grants per fiscal year.

    Shows how much the abstract text search contributes — critical for
    understanding data quality in sparse years (FY2005-06, FY2013, FY2018).
    """
    yearly = (
        df.groupby(["FY", "MATCH_SOURCE"])
        .agg(
            funding=("TOTAL_COST", "sum"),
            count=("APPLICATION_ID", "count"),
        )
        .reset_index()
    )

    pivot_funding = yearly.pivot(
        index="FY", columns="MATCH_SOURCE", values="funding"
    ).fillna(0)
    pivot_count = yearly.pivot(
        index="FY", columns="MATCH_SOURCE", values="count"
    ).fillna(0)

    # Ensure both columns exist
    for col in ["keywords_only", "abstract_only"]:
        if col not in pivot_funding.columns:
            pivot_funding[col] = 0.0
            pivot_count[col] = 0

    renderer.match_source_breakdown(pivot_funding, "match_source_breakdown.png")

    return {
        "years": pivot_funding.index.tolist(),
        "keyword_funding": pivot_funding["keywords_only"].tolist(),
        "abstract_funding": pivot_funding["abstract_only"].tolist(),
        "keyword_count": [int(x) for x in pivot_count["keywords_only"].tolist()],
        "abstract_count": [int(x) for x in pivot_count["abstract_only"].tolist()],
    }


def mechanism_breakdown(df: pd.DataFrame, renderer) -> dict:
    """Chart 6: Funding by grant mechanism (R, P, U, K, T, F, Other).

    Shows how biomarker research distributes across different NIH funding
    mechanisms — R01s vs center grants vs cooperative agreements.
    """
    df = df.copy()
    df["mechanism"] = df["ACTIVITY"].apply(activity_category)

    # Overall breakdown
    mech = (
        df.groupby("mechanism")
        .agg(
            total_funding=("TOTAL_COST", "sum"),
            grant_count=("APPLICATION_ID", "count"),
        )
        .reset_index()
        .sort_values("total_funding", ascending=False)
    )

    # Core vs expanded per mechanism
    core_mech = (
        df[df["EXPLICIT_BIOMARKER"]]
        .groupby("mechanism")
        .agg(core_funding=("TOTAL_COST", "sum"), core_count=("APPLICATION_ID", "count"))
        .reset_index()
    )
    mech = mech.merge(core_mech, on="mechanism", how="left").fillna(0)
    mech["expanded_funding"] = mech["total_funding"] - mech["core_funding"]

    # Over time by mechanism
    yearly_mech = df.groupby(["FY", "mechanism"])["TOTAL_COST"].sum().reset_index()
    pivot = yearly_mech.pivot(
        index="FY", columns="mechanism", values="TOTAL_COST"
    ).fillna(0)

    renderer.mechanism_breakdown(mech, pivot, "mechanism_breakdown.png")

    return {
        "mechanisms": mech[
            [
                "mechanism",
                "total_funding",
                "grant_count",
                "core_funding",
                "core_count",
                "expanded_funding",
            ]
        ].to_dict(orient="records"),
        "over_time": {
            "years": pivot.index.tolist(),
            "mechanisms": {col: pivot[col].tolist() for col in pivot.columns},
        },
    }


def keyword_funding(df: pd.DataFrame, renderer, n_top: int = 15) -> dict:
    """Chart 7: Funding by primary keyword term (top N).

    Uses TERM_PRIORITY to assign each grant a single non-overlapping term,
    then shows funding distribution across the most common terms.
    """
    # Filter to grants with a primary term
    has_term = df[df["PRIMARY_TERM"].notna() & (df["PRIMARY_TERM"] != "")].copy()

    term_funding = (
        has_term.groupby("PRIMARY_TERM")
        .agg(
            total_funding=("TOTAL_COST", "sum"),
            grant_count=("APPLICATION_ID", "count"),
        )
        .reset_index()
        .sort_values("total_funding", ascending=False)
    )

    top_terms = term_funding.head(n_top)

    renderer.keyword_funding(top_terms, "keyword_funding.png")

    return {
        "terms": top_terms.to_dict(orient="records"),
        "total_with_term": len(has_term),
        "total_without_term": len(df) - len(has_term),
    }


def core_vs_expanded_terms(df: pd.DataFrame, renderer) -> dict:
    """Chart 8: Two-panel — funding by keyword for core vs expanded-only grants.

    Left panel: grants with EXPLICIT_BIOMARKER=TRUE ($62B). Shows the highest-priority
    CORE term each grant matched (not the most-specific expanded term). This avoids
    showing expanded terms like "digital biomarker" in the core panel.

    Right panel: grants with EXPLICIT_BIOMARKER=FALSE ($113B). Shows PRIMARY_TERM
    (most specific expanded term).

    No double counting: every grant appears in exactly one panel.
    """
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
    from keyword_terms import CORE_BIOMARKER_TERMS, TERM_PRIORITY

    core_set = set(CORE_BIOMARKER_TERMS)
    # Core-only priority: just the core terms, in TERM_PRIORITY order
    core_priority = [t for t in TERM_PRIORITY if t in core_set]

    has_term = df[df["PRIMARY_TERM"].notna() & (df["PRIMARY_TERM"] != "")].copy()

    # Split by EXPLICIT_BIOMARKER — matches $62B/$113B split used elsewhere
    core_grants = has_term[has_term["EXPLICIT_BIOMARKER"]].copy()
    expanded_grants = has_term[~has_term["EXPLICIT_BIOMARKER"]]

    # For core grants: assign the highest-priority CORE term they matched
    def best_core_term(matched_terms_str):
        if pd.isna(matched_terms_str) or matched_terms_str == "":
            return "biomarker"
        terms = matched_terms_str.split(";")
        for t in core_priority:
            if t in terms:
                return t
        return "biomarker"

    core_grants["CORE_PRIMARY"] = core_grants["MATCHED_TERMS"].apply(best_core_term)

    core_df = (
        core_grants.groupby("CORE_PRIMARY")
        .agg(
            total_funding=("TOTAL_COST", "sum"), grant_count=("APPLICATION_ID", "count")
        )
        .reset_index()
        .rename(columns={"CORE_PRIMARY": "PRIMARY_TERM"})
        .sort_values("total_funding", ascending=False)
    )

    # For expanded-only grants: group into 3 categories
    expanded_grants = expanded_grants.copy()

    def expanded_category(term):
        if term == "clinical+omics":
            return "clinical+omics"
        elif term == "clinical+imaging":
            return "clinical+imaging"
        else:
            return "Other precision medicine terms"

    expanded_grants["exp_category"] = expanded_grants["PRIMARY_TERM"].apply(
        expanded_category
    )
    expanded_df = (
        expanded_grants.groupby("exp_category")
        .agg(
            total_funding=("TOTAL_COST", "sum"), grant_count=("APPLICATION_ID", "count")
        )
        .reset_index()
        .rename(columns={"exp_category": "PRIMARY_TERM"})
        .sort_values("total_funding", ascending=False)
    )

    renderer.core_vs_expanded_terms(core_df, expanded_df, "core_vs_expanded_terms.png")

    return {
        "core_terms": core_df.to_dict(orient="records"),
        "expanded_terms": expanded_df.to_dict(orient="records"),
        "core_total_funding": float(core_df["total_funding"].sum()),
        "expanded_total_funding": float(expanded_df["total_funding"].sum()),
        "core_total_grants": int(core_df["grant_count"].sum()),
        "expanded_total_grants": int(expanded_df["grant_count"].sum()),
    }


def term_by_mechanism(df: pd.DataFrame, renderer) -> dict:
    """Chart 9: Keyword term × grant mechanism cross-tabulation.

    Explodes MATCHED_TERMS so a grant matching multiple terms counts in each
    term's row. Shows which grant mechanisms fund which keyword terms.
    This intentionally double-counts multi-term grants — the question is
    "which mechanisms fund grants mentioning surrogate endpoint", not
    "which mechanisms fund grants whose primary term is surrogate endpoint."
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

    renderer.term_by_mechanism(pivot_funding, pivot_count, "term_by_mechanism.png")

    # Compute R-grant percentage for each term
    r_col = "Research (R)" if "Research (R)" in pivot_funding.columns else None
    r_pct = {}
    if r_col:
        for term in pivot_funding.index:
            total = pivot_funding.loc[term].sum()
            r_pct[term] = round(
                100 * pivot_funding.loc[term, r_col] / total, 1
            ) if total > 0 else 0

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

    print("1. Total biomarker spending over time (core vs expanded)...")
    results["spending_over_time"] = spending_over_time(df, renderer)

    print("\n2. Institute allocation (with core/expanded split)...")
    results["institute_allocation"] = institute_allocation(df, renderer)

    print("\n3. Institute funding over time...")
    results["institute_over_time"] = institute_over_time(df, renderer)

    print("\n4. Explicit biomarker adoption rate...")
    results["explicit_adoption"] = explicit_adoption(df, renderer)

    print("\n5. Match source breakdown (keyword vs abstract)...")
    results["match_source_breakdown"] = match_source_breakdown(df, renderer)

    print("\n6. Mechanism breakdown...")
    results["mechanism_breakdown"] = mechanism_breakdown(df, renderer)

    print("\n7. Funding by keyword term...")
    results["keyword_funding"] = keyword_funding(df, renderer)

    print("\n8. Core vs expanded terms (two-panel)...")
    results["core_vs_expanded_terms"] = core_vs_expanded_terms(df, renderer)

    print("\n9. Term × grant mechanism...")
    results["term_by_mechanism"] = term_by_mechanism(df, renderer)

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
