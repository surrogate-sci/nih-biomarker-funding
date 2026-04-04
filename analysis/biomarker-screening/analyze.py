#!/usr/bin/env python3
"""Biomarker Screening Analysis — dataset characterization for policy narrative.

Produces 5 charts addressing the question: what kind of biomarker work does NIH
fund, and is surrogacy/endpoint validation an afterthought?

Charts:
1. Total biomarker spending over time (core vs expanded stacked)
2. Funding allocation by institute (top 10, with core/expanded split)
3. Biomarker purpose distribution — funding by functional category
4. Biomarker purpose over time — trends by category (surrogacy flat?)
5. Purpose × grant mechanism — where surrogacy validation (doesn't) happen

Uses Datawrapper if DATAWRAPPER_API_TOKEN is set, else seaborn/matplotlib.
Outputs: charts/ directory + funding_analysis.json
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

from charts import get_renderer
from utils import (
    DATA_QUALITY_YEARS,
    PURPOSE_ORDER,
    TERM_PURPOSE,
    activity_category,
    load_dataset,
)

CHARTS_DIR = Path(__file__).parent / "charts"


def _assign_purpose(df: pd.DataFrame) -> pd.DataFrame:
    """Add PURPOSE column based on PRIMARY_TERM → TERM_PURPOSE mapping."""
    df = df.copy()
    df["PURPOSE"] = df["PRIMARY_TERM"].map(TERM_PURPOSE).fillna("Unclassified")
    return df


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
        "core_count": [int(x) for x in yearly["core_count"].tolist()],
        "expanded_count": [int(x) for x in yearly["expanded_count"].tolist()],
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


def purpose_distribution(df: pd.DataFrame, renderer) -> dict:
    """Chart 3: Funding by biomarker purpose category.

    Scoped to grants where PURPOSE is determinable from title keywords (grants
    with a non-empty PRIMARY_TERM). The remaining grants matched via PROJECT_TERMS
    or abstract text — their purpose requires LLM grading to determine.

    This scoping IS the finding: most biomarker grants don't use specific enough
    language in their title to classify, and among those that do, surrogacy/endpoint
    validation is nearly absent.
    """
    classified = df[df["PURPOSE"] != "Unclassified"]
    unclassified_n = (df["PURPOSE"] == "Unclassified").sum()
    unclassified_funding = df.loc[df["PURPOSE"] == "Unclassified", "TOTAL_COST"].sum()

    purpose = (
        classified.groupby("PURPOSE")
        .agg(
            total_funding=("TOTAL_COST", "sum"),
            grant_count=("APPLICATION_ID", "count"),
        )
        .reset_index()
    )

    # Order by PURPOSE_ORDER
    purpose["sort_key"] = purpose["PURPOSE"].map(
        {p: i for i, p in enumerate(PURPOSE_ORDER)}
    )
    purpose = purpose.sort_values("sort_key").drop(columns="sort_key")

    classified_funding = classified["TOTAL_COST"].sum()
    purpose["pct"] = (100 * purpose["total_funding"] / classified_funding).round(1)

    renderer.purpose_distribution(purpose, "purpose_distribution.png")

    return {
        "categories": purpose.to_dict(orient="records"),
        "classified_grants": len(classified),
        "classified_funding": float(classified_funding),
        "unclassified_grants": int(unclassified_n),
        "unclassified_funding": float(unclassified_funding),
    }


def purpose_over_time(df: pd.DataFrame, renderer) -> dict:
    """Chart 4: Biomarker purpose trends over time.

    Scoped to classified grants only (title-matched). Shows how each purpose
    category grew (or didn't). Surrogacy & endpoint validation should be flat/tiny.
    """
    classified = df[df["PURPOSE"] != "Unclassified"]
    yearly = classified.groupby(["FY", "PURPOSE"])["TOTAL_COST"].sum().reset_index()
    pivot = yearly.pivot(index="FY", columns="PURPOSE", values="TOTAL_COST").fillna(0)

    # Reorder columns by PURPOSE_ORDER (no Unclassified)
    cols = [c for c in PURPOSE_ORDER if c in pivot.columns]
    pivot = pivot[cols]

    renderer.purpose_over_time(pivot, "purpose_over_time.png")

    return {
        "years": pivot.index.tolist(),
        "categories": {col: pivot[col].tolist() for col in pivot.columns},
    }


def purpose_by_mechanism(df: pd.DataFrame, renderer) -> dict:
    """Chart 5: Purpose × grant mechanism cross-tabulation.

    Scoped to classified grants. Shows how surrogacy validation distributes
    across R01s, cooperative agreements, center grants, etc. — directly
    addressing whether validation work happens in investigator-initiated research.
    """
    df = df[df["PURPOSE"] != "Unclassified"].copy()
    df["mechanism"] = df["ACTIVITY"].apply(activity_category)

    cross = (
        df.groupby(["PURPOSE", "mechanism"])
        .agg(
            total_funding=("TOTAL_COST", "sum"),
            grant_count=("APPLICATION_ID", "count"),
        )
        .reset_index()
    )

    # Pivot: rows = purpose, columns = mechanism
    pivot_funding = cross.pivot(
        index="PURPOSE", columns="mechanism", values="total_funding"
    ).fillna(0)

    pivot_count = cross.pivot(
        index="PURPOSE", columns="mechanism", values="grant_count"
    ).fillna(0)

    # Order rows by PURPOSE_ORDER
    row_order = [p for p in PURPOSE_ORDER if p in pivot_funding.index]
    for p in pivot_funding.index:
        if p not in row_order:
            row_order.append(p)
    pivot_funding = pivot_funding.loc[row_order]
    pivot_count = pivot_count.loc[row_order]

    # Column order: largest mechanism first
    col_order = pivot_funding.sum().sort_values(ascending=False).index.tolist()
    pivot_funding = pivot_funding[col_order]
    pivot_count = pivot_count[col_order]

    renderer.purpose_by_mechanism(pivot_funding, pivot_count, "purpose_by_mechanism.png")

    return {
        "funding": {
            p: {m: float(pivot_funding.loc[p, m]) for m in pivot_funding.columns}
            for p in pivot_funding.index
        },
        "counts": {
            p: {m: int(pivot_count.loc[p, m]) for m in pivot_count.columns}
            for p in pivot_count.index
        },
    }


def main():
    print("Loading dataset...")
    df = load_dataset()
    print(f"  {len(df):,} grants loaded")

    total_b = df["TOTAL_COST"].sum()
    print(f"  Total funding: ${total_b / 1e9:.2f}B")
    print(f"  EXPLICIT_BIOMARKER=TRUE: {df['EXPLICIT_BIOMARKER'].sum():,}")
    print(f"  PRIMARY_TERM populated: {(df['PRIMARY_TERM'] != '').sum():,}")

    # Assign purpose categories
    df = _assign_purpose(df)
    unclassified = (df["PURPOSE"] == "Unclassified").sum()
    if unclassified:
        print(f"  WARNING: {unclassified:,} grants have no PURPOSE (missing PRIMARY_TERM)")

    renderer = get_renderer(CHARTS_DIR)
    print(f"  Using {renderer.backend} renderer\n")

    results = {}

    print("1. Total biomarker spending over time (core vs expanded)...")
    results["spending_over_time"] = spending_over_time(df, renderer)

    print("\n2. Institute allocation (with core/expanded split)...")
    results["institute_allocation"] = institute_allocation(df, renderer)

    print("\n3. Biomarker purpose distribution...")
    results["purpose_distribution"] = purpose_distribution(df, renderer)

    print("\n4. Biomarker purpose over time...")
    results["purpose_over_time"] = purpose_over_time(df, renderer)

    print("\n5. Purpose × grant mechanism...")
    results["purpose_by_mechanism"] = purpose_by_mechanism(df, renderer)

    # Summary stats
    explicit_df = df[df["EXPLICIT_BIOMARKER"]]
    classified = df[df["PURPOSE"] != "Unclassified"]
    unclassified = df[df["PURPOSE"] == "Unclassified"]

    surrogacy = df[df["PURPOSE"] == "Surrogacy & endpoint validation"]
    decision = df[df["PURPOSE"] == "Clinical decision-making"]

    results["summary"] = {
        "total_grants": len(df),
        "total_funding_billions": round(df["TOTAL_COST"].sum() / 1e9, 2),
        "explicit_grants": int(df["EXPLICIT_BIOMARKER"].sum()),
        "explicit_funding_billions": round(explicit_df["TOTAL_COST"].sum() / 1e9, 2),
        "classified_grants": len(classified),
        "classified_funding_billions": round(classified["TOTAL_COST"].sum() / 1e9, 2),
        "unclassified_grants": len(unclassified),
        "unclassified_funding_billions": round(unclassified["TOTAL_COST"].sum() / 1e9, 2),
        "surrogacy_grants": len(surrogacy),
        "surrogacy_funding_billions": round(surrogacy["TOTAL_COST"].sum() / 1e9, 2),
        "surrogacy_pct_of_classified": round(
            100 * surrogacy["TOTAL_COST"].sum() / classified["TOTAL_COST"].sum(), 2
        )
        if len(classified) > 0
        else 0,
        "decision_grants": len(decision),
        "decision_funding_billions": round(decision["TOTAL_COST"].sum() / 1e9, 2),
        "year_range": [int(df["FY"].min()), int(df["FY"].max())],
        "data_quality_years": sorted(DATA_QUALITY_YEARS),
        "renderer": renderer.backend,
    }

    out_path = CHARTS_DIR / "funding_analysis.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")

    # Print headline finding
    s = results["summary"]
    print(f"\n{'='*60}")
    print(f"HEADLINE: Of {s['classified_grants']:,} title-classifiable grants:")
    print(f"  Surrogacy & endpoint validation = {s['surrogacy_grants']:,} grants")
    print(f"    ${s['surrogacy_funding_billions']:.2f}B of ${s['classified_funding_billions']:.1f}B classified")
    print(f"    ({s['surrogacy_pct_of_classified']:.1f}% of classified funding)")
    print(f"  {s['unclassified_grants']:,} grants (${s['unclassified_funding_billions']:.1f}B)")
    print(f"    matched via structured fields/abstract — purpose requires LLM grading")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
